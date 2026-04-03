import logging

import discord
from discord import ApplicationContext, Interaction, Option, WebhookMessage, slash_command
from discord.ext import commands
from discord.ext.commands import has_any_role

from src.bot import Bot
from src.core import settings
from src.database.models.dynamic_role import RoleCategory

logger = logging.getLogger(__name__)

CATEGORY_CHOICES = [c.value for c in RoleCategory]


class RoleAdminCog(commands.Cog):
    """Admin commands for managing dynamic Discord roles."""

    def __init__(self, bot: Bot):
        self.bot = bot

    role_admin = discord.SlashCommandGroup(
        "role-admin",
        "Manage dynamic Discord roles",
        guild_ids=settings.guild_ids,
    )

    @role_admin.command(description="Add a new dynamic role.")
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

    @role_admin.command(description="Remove a dynamic role.")
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

    @role_admin.command(description="Update a dynamic role's Discord role.")
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

    @role_admin.command(description="List configured dynamic roles.")
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

    @role_admin.command(description="Force reload dynamic roles from database.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"))
    async def reload(self, ctx: ApplicationContext) -> Interaction | WebhookMessage:
        """Force reload the role manager cache from the database."""
        await self.bot.role_manager.reload()
        return await ctx.respond("Dynamic roles reloaded from database.", ephemeral=True)


def setup(bot: Bot) -> None:
    """Load the `RoleAdminCog` cog."""
    bot.add_cog(RoleAdminCog(bot))
