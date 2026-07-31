"""Admin command group for bot administration commands."""

import logging
import re
from datetime import datetime

import discord
from discord import ApplicationContext, Interaction, Option, WebhookMessage
from discord.ext import commands
from discord.ext.commands import has_any_role
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.bot import Bot
from src.core import settings
from src.database.models import AnonymousVoteCandidate, AnonymousVoteSession
from src.database.models.dynamic_role import RoleCategory
from src.database.session import AsyncSessionLocal
from src.helpers.duration import validate_duration
from src.views.anonymous_vote import (
    AnonymousVoteView,
    build_poll_embed,
    schedule_vote_close,
)

logger = logging.getLogger(__name__)

CATEGORY_CHOICES = [c.value for c in RoleCategory]
_MEMBER_TOKEN_RE = re.compile(r"<@!?(\d+)>|^(\d+)$")


def _parse_member_ids(raw: str) -> list[int]:
    """Parse space/comma-separated mentions or snowflake IDs into unique IDs."""
    ids: list[int] = []
    for part in re.split(r"[\s,]+", raw.strip()):
        if not part:
            continue
        match = _MEMBER_TOKEN_RE.fullmatch(part)
        if not match:
            raise ValueError(
                f"Could not parse `{part}`. Use mentions or numeric user IDs."
            )
        ids.append(int(match.group(1) or match.group(2)))
    # Preserve order, drop duplicates
    return list(dict.fromkeys(ids))


class AdminCog(commands.Cog):
    """Admin commands for bot administration."""

    def __init__(self, bot: Bot):
        self.bot = bot

    admin = discord.SlashCommandGroup(
        "admin",
        "Bot administration commands",
        guild_ids=settings.guild_ids,
    )

    role = admin.create_subgroup(
        "role",
        "Manage dynamic Discord roles",
    )

    @role.command(description="Add a new dynamic role.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"))
    async def add(
        self,
        ctx: ApplicationContext,
        category: Option(str, "Role category", choices=CATEGORY_CHOICES),
        key: Option(str, "Lookup key (e.g. 'Omniscient', 'CWPE')"),
        role: Option(discord.Role, "The Discord role"),
        display_name: Option(str, "Human-readable name"),
        description: Option(str, "Description (for joinable roles)", required=False),
        cert_full_name: Option(str, "Full cert name from HTB platform (academy_cert only)", required=False),
        cert_integer_id: Option(int, "Platform cert ID (academy_cert only)", required=False),
    ) -> Interaction | WebhookMessage:
        """Add a new dynamic role to the database."""
        try:
            cat = RoleCategory(category)
        except ValueError:
            return await ctx.respond(f"Invalid category: {category}", ephemeral=True)

        await self.bot.role_manager.add_role(
            key=key,
            category=cat,
            discord_role_id=role.id,
            display_name=display_name,
            description=description,
            cert_full_name=cert_full_name,
            cert_integer_id=cert_integer_id,
        )
        return await ctx.respond(
            f"Added dynamic role: `{category}/{key}` -> {role.mention}",
            ephemeral=True,
        )

    @role.command(description="Remove a dynamic role.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"))
    async def remove(
        self,
        ctx: ApplicationContext,
        category: Option(str, "Role category", choices=CATEGORY_CHOICES),
        key: Option(str, "Lookup key to remove"),
    ) -> Interaction | WebhookMessage:
        """Remove a dynamic role from the database."""
        try:
            cat = RoleCategory(category)
        except ValueError:
            return await ctx.respond(f"Invalid category: {category}", ephemeral=True)

        deleted = await self.bot.role_manager.remove_role(cat, key)
        if deleted:
            return await ctx.respond(f"Removed dynamic role: `{category}/{key}`", ephemeral=True)
        return await ctx.respond(f"No role found for `{category}/{key}`", ephemeral=True)

    @role.command(description="Update a dynamic role's Discord role.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"))
    async def update(
        self,
        ctx: ApplicationContext,
        category: Option(str, "Role category", choices=CATEGORY_CHOICES),
        key: Option(str, "Lookup key to update"),
        role: Option(discord.Role, "The new Discord role"),
    ) -> Interaction | WebhookMessage:
        """Update a dynamic role's Discord ID."""
        try:
            cat = RoleCategory(category)
        except ValueError:
            return await ctx.respond(f"Invalid category: {category}", ephemeral=True)

        updated = await self.bot.role_manager.update_role(cat, key, role.id)
        if updated:
            return await ctx.respond(
                f"Updated `{category}/{key}` -> {role.mention}",
                ephemeral=True,
            )
        return await ctx.respond(f"No role found for `{category}/{key}`", ephemeral=True)

    @role.command(description="List configured dynamic roles.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_MODS"))
    async def list(
        self,
        ctx: ApplicationContext,
        category: Option(str, "Filter by category", choices=CATEGORY_CHOICES, required=False),
    ) -> Interaction | WebhookMessage:
        """List all configured dynamic roles."""
        cat = RoleCategory(category) if category else None
        roles = await self.bot.role_manager.list_roles(cat)

        if not roles:
            return await ctx.respond("No dynamic roles configured.", ephemeral=True)

        # Group by category for display
        grouped: dict[str, list[str]] = {}
        for r in roles:
            cat_name = r.category.value
            if cat_name not in grouped:
                grouped[cat_name] = []
            guild_role = ctx.guild.get_role(r.discord_role_id)
            role_mention = guild_role.mention if guild_role else f"`{r.discord_role_id}`"
            grouped[cat_name].append(f"`{r.key}` -> {role_mention} ({r.display_name})")

        embed = discord.Embed(title="Dynamic Roles", color=0x9ACC14)
        for cat_name, entries in grouped.items():
            embed.add_field(
                name=cat_name,
                value="\n".join(entries[:10]) + (f"\n... and {len(entries) - 10} more" if len(entries) > 10 else ""),
                inline=False,
            )

        return await ctx.respond(embed=embed, ephemeral=True)

    @role.command(description="Force reload dynamic roles from database.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"))
    async def reload(self, ctx: ApplicationContext) -> Interaction | WebhookMessage:
        """Force reload the role manager cache from the database."""
        await self.bot.role_manager.reload()
        return await ctx.respond("Dynamic roles reloaded from database.", ephemeral=True)

    @admin.command(
        name="vote",
        description="Start an anonymous timed vote on multiple members.",
    )
    @has_any_role(*settings.role_groups.get("VOTE_STARTERS"))
    async def vote(
        self,
        ctx: ApplicationContext,
        members: Option(
            str,
            "Nominees as mentions or user IDs (space/comma separated, max 25)",
        ),
        duration: Option(str, "How long the vote stays open (e.g. 12h, 1d, 30m)"),
        topic: Option(str, "Optional topic shown on the poll", required=False),
    ) -> Interaction | WebhookMessage:
        """Start an anonymous vote; tallies reveal automatically when duration ends."""
        closes_at_ts, error = validate_duration(duration)
        if error:
            return await ctx.respond(error, ephemeral=True)

        try:
            member_ids = _parse_member_ids(members)
        except ValueError as exc:
            return await ctx.respond(str(exc), ephemeral=True)

        if not member_ids:
            return await ctx.respond("Provide at least one nominee.", ephemeral=True)
        if len(member_ids) > 25:
            return await ctx.respond(
                "Discord select menus support at most 25 nominees.",
                ephemeral=True,
            )

        resolved: list[tuple[int, str]] = []
        missing: list[str] = []
        for user_id in member_ids:
            member = ctx.guild.get_member(user_id)
            if member is None:
                try:
                    member = await ctx.guild.fetch_member(user_id)
                except discord.HTTPException:
                    missing.append(str(user_id))
                    continue
            resolved.append((member.id, member.display_name))

        if missing:
            return await ctx.respond(
                "Could not find member(s) in this server: " + ", ".join(f"`{m}`" for m in missing),
                ephemeral=True,
            )

        closes_at = datetime.fromtimestamp(closes_at_ts)
        await ctx.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            vote_session = AnonymousVoteSession(
                guild_id=ctx.guild.id,
                channel_id=ctx.channel.id,
                message_id=None,
                topic=topic,
                created_by_id=ctx.author.id,
                closes_at=closes_at,
                closed=False,
            )
            session.add(vote_session)
            await session.flush()

            for user_id, display_name in resolved:
                session.add(
                    AnonymousVoteCandidate(
                        session_id=vote_session.id,
                        user_id=user_id,
                        display_name=display_name,
                    )
                )
            await session.commit()

            loaded = await session.scalar(
                select(AnonymousVoteSession)
                .where(AnonymousVoteSession.id == vote_session.id)
                .options(selectinload(AnonymousVoteSession.candidates))
            )
            session_id = loaded.id
            candidates = list(loaded.candidates)
            poll_embed = build_poll_embed(loaded, candidates)

        view = AnonymousVoteView(session_id, self.bot, candidates)
        self.bot.add_view(view)
        message = await ctx.channel.send(embed=poll_embed, view=view)

        async with AsyncSessionLocal() as session:
            vote_session = await session.get(AnonymousVoteSession, session_id)
            if vote_session:
                vote_session.message_id = message.id
                await session.commit()

        schedule_vote_close(self.bot, session_id, closes_at)
        return await ctx.followup.send(
            f"Anonymous vote #{session_id} started in {ctx.channel.mention}. "
            f"Closes {discord.utils.format_dt(closes_at, style='R')}.",
            ephemeral=True,
        )


def setup(bot: Bot) -> None:
    """Load the AdminCog."""
    bot.add_cog(AdminCog(bot))
