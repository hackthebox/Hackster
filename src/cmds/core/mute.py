import asyncio
import logging
from datetime import datetime

from discord import ApplicationContext, Guild, Interaction, Member, WebhookMessage, slash_command
from discord.errors import Forbidden
from discord.ext import commands
from discord.ext.commands import has_any_role
from sqlalchemy.exc import NoResultFound

from src.bot import Bot
from src.core import settings
from src.database.models import Mute
from src.database.session import AsyncSessionLocal
from src.helpers.ban import unmute_member
from src.helpers.checks import member_is_staff
from src.helpers.duration import validate_duration
from src.helpers.schedule import schedule

logger = logging.getLogger(__name__)


class MuteCog(commands.Cog):
    """Mute related commands."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self._pending_tasks: set[asyncio.Task] = set()

    def _schedule_unmute(self, guild: Guild, member: Member, run_at: datetime) -> None:
        """Unmute `member` at `run_at`, keeping a reference so the task cannot be collected."""
        task = self.bot.loop.create_task(self._unmute_when_due(guild, member, run_at))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _unmute_when_due(self, guild: Guild, member: Member, run_at: datetime) -> None:
        """Remove the mute when its duration elapses."""
        try:
            await schedule(unmute_member(guild, member), run_at=run_at)
        except NoResultFound:
            logger.info("Mute for user_id %s was already removed.", member.id)
        except Exception:
            logger.exception("Failed to unmute user_id %s.", member.id)

    @slash_command(
        guild_ids=settings.guild_ids,
        description="Mute a person (adds the Muted role to person)."
    )
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_MODS"))
    async def mute(
        self, ctx: ApplicationContext, user: Member, duration: str, reason: str
    ) -> Interaction | WebhookMessage:
        """Mute a person (adds the Muted role to person)."""
        member = await self.bot.get_member_or_user(ctx.guild, user.id)
        if not member:
            return await ctx.respond(f"User {user} not found.")
        if isinstance(member, Member):
            if member_is_staff(member):
                return await ctx.respond("You cannot mute another staff member.")
        if member.bot:
            return await ctx.respond("You cannot mute a bot.")

        dur, dur_exc = validate_duration(duration)
        if dur_exc:
            return await ctx.respond(dur_exc, delete_after=15)

        async with AsyncSessionLocal() as session:
            mute_ = Mute(
                user_id=member.id,
                reason=reason if reason else "Time to shush, innit?",
                moderator_id=ctx.user.id,
                unmute_time=dur,
            )
            session.add(mute_)
            await session.commit()

        if isinstance(member, Member):
            role = ctx.guild.get_role(settings.roles.MUTED)
            await member.add_roles(role)
        timestamp = datetime.fromtimestamp(dur)
        self._schedule_unmute(ctx.guild, member, timestamp)
        await member.timeout(timestamp, reason=reason if reason else "Time to shush, innit?")
        try:
            await member.send(f"You have been muted for {duration}. Reason:\n>>> {reason}")
        except Forbidden:
            return await ctx.respond(
                f"{member.mention} ({member.id}) has been muted for {duration}, but cannot DM due to their privacy "
                f"settings."
            )

        return await ctx.respond(f"{member.mention} ({member.id}) has been muted for {duration}.")

    @slash_command(
        guild_ids=settings.guild_ids, description="Unmute the user removing the Muted role."
    )
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_MODS"))
    async def unmute(self, ctx: ApplicationContext, user: Member) -> Interaction | WebhookMessage:
        """Unmute the user removing the Muted role."""
        member = await self.bot.get_member_or_user(ctx.guild, user.id)

        if member is None:
            return await ctx.respond("Error: Cannot retrieve member.")

        await unmute_member(ctx.guild, member)
        return await ctx.respond(f"{member.mention} ({member.id}) has been unmuted.")


def setup(bot: Bot) -> None:
    """Load the `MuteCog` cog."""
    bot.add_cog(MuteCog(bot))
