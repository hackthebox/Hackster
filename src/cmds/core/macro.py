import logging
from typing import Sequence

import arrow
from discord import ApplicationContext, Embed, Interaction, SlashCommandGroup, WebhookMessage
from discord.abc import GuildChannel
from discord.ext import commands
from discord.ext.commands import has_any_role
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.bot import Bot
from src.core import settings
from src.database.models import Macro
from src.database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)


class MacroCog(commands.Cog):
    """Manage macro's."""

    def __init__(self, bot: Bot):
        self.bot = bot

    macro = SlashCommandGroup("macro", "Manage macro's.", guild_ids=settings.guild_ids)

    @macro.command(description="Add a macro to the records.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_HTB_STAFF"))
    async def add(self, ctx: ApplicationContext, name: str, text: str) -> Interaction | WebhookMessage:
        """Add a macro to the records."""
        if len(text) == 0:
            return await ctx.respond("The macro is empty. Try again...", ephemeral=True)

        if len(name) == 0:
            return await ctx.respond("The macro name is empty. Try again...", ephemeral=True)

        # Name should be lowercase.
        name = name.lower()

        moderator_id = ctx.user.id
        today = arrow.utcnow().format("YYYY-MM-DD HH:mm:ss")
        macro = Macro(user_id=moderator_id, name=name, text=text, created_at=today)
        async with AsyncSessionLocal() as session:
            try:
                session.add(macro)
                await session.commit()
                return await ctx.respond(f"Macro {name} added. ID: {macro.id}", ephemeral=True)
            except IntegrityError:
                return await ctx.respond(f"Macro with the name '{name}' already exists.", ephemeral=True)

    @macro.command(description="Remove a macro by providing the ID to remove.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_HTB_STAFF"))
    async def remove(self, ctx: ApplicationContext, macro_id: int) -> Interaction | WebhookMessage:
        """Remove a macro by providing ID to remove."""
        async with AsyncSessionLocal() as session:
            macro = await session.get(Macro, macro_id)
            if macro:
                await session.delete(macro)
                await session.commit()
                return await ctx.respond(f"Macro #{macro_id} ({macro.name}) has been deleted.", ephemeral=True)
            else:
                return await ctx.respond(f"Macro #{macro_id} has not been found.", ephemeral=True)

    @macro.command(description="Edit a macro by providing the ID to edit.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_HTB_STAFF"))
    async def edit(self, ctx: ApplicationContext, macro_id: int, text: str) -> Interaction | WebhookMessage:
        """Edit a macro by providing the ID to edit."""
        async with AsyncSessionLocal() as session:
            stmt = select(Macro).filter(Macro.id == macro_id)
            result = await session.scalars(stmt)
            macro: Macro = result.first()
            if macro:
                macro.text = text
                await session.commit()
                return await ctx.respond(f"Macro #{macro_id} has been updated.", ephemeral=True)
            else:
                return await ctx.respond(f"Macro #{macro_id} has not been found.", ephemeral=True)

    @macro.command(description="List all macro's.")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def list(self, ctx: ApplicationContext) -> Interaction | WebhookMessage:
        """List all macro's."""
        async with AsyncSessionLocal() as session:
            stmt = select(Macro)
            result = await session.scalars(stmt)
            macros: Sequence[Macro] = result.all()
            # If no macros are returned, show a message.
            if not macros:
                return await ctx.respond("No macros have been added yet.")

            embed = Embed(title="Macros", description="List of all macros.")
            for macro in macros:
                embed.add_field(name=f"Macro #{macro.id} - name: {macro.name}", value=macro.text, inline=False)
            return await ctx.respond(embed=embed, ephemeral=True)

    @macro.command(description="Send text from a macro by providing the name.")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def send(self,
                   ctx: ApplicationContext,
                   name: str,
                   channel: GuildChannel = None
                   ) -> Interaction | WebhookMessage:
        """Send text from a macro by providing the name If a mod or higher, they can send to a remote channel."""
        name = name.lower()
        async with AsyncSessionLocal() as session:
            stmt = select(Macro).filter(Macro.name == name)
            result = await session.scalars(stmt)
            macro: Macro = result.first()

            if not macro:
                return await ctx.respond(f"Macro #{name} has not been found. "
                                         "Check the list of macros via the command `/macro list`.", ephemeral=True)

            if channel:
                allowed_roles = {role.id for role in ctx.user.roles}
                required_roles = set(
                    settings.role_groups.get("ALL_ADMINS", [])
                    + settings.role_groups.get("ALL_HTB_STAFF", [])
                    + settings.role_groups.get("ALL_MODS", [])
                )
                if allowed_roles & required_roles:
                    await channel.send(f"{macro.text}")
                    return await ctx.respond(f"Macro {name} has been sent to {channel.mention}.", ephemeral=True)
                return await ctx.respond("You don't have permission to send macros in other channels.",
                                         ephemeral=True)
            return await ctx.respond(f"{macro.text}")

    @macro.command(description="Instructions for the macro commands.")
    async def help(self, ctx: ApplicationContext) -> Interaction | WebhookMessage:
        """Send instructions from the macro functionalities."""
        embed = Embed(title="Macro Help", description="Instructions for the macro commands.")
        embed.add_field(name="Add a macro", value="`/macro add <name> <text>`", inline=False)
        embed.add_field(name="Remove a macro", value="`/macro remove <id>`", inline=False)
        embed.add_field(name="Edit a macro", value="`/macro edit <id> <text>`", inline=False)
        embed.add_field(name="List all macros", value="`/macro list`", inline=False)
        embed.add_field(name="Send a macro", value="`/macro send <name> [channel]` (channel=optional)", inline=False)
        return await ctx.respond(embed=embed, ephemeral=True)


def setup(bot: Bot) -> None:
    """Load the `MacroCog` cog."""
    bot.add_cog(MacroCog(bot))
