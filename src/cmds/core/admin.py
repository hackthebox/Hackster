"""Admin command group for bot administration commands."""

import logging

import discord
from discord.ext import commands

from src.bot import Bot
from src.core import settings

logger = logging.getLogger(__name__)

# Top-level admin command group
# Subcommands (like 'role') are registered by other cogs using admin.create_subgroup()
admin = discord.SlashCommandGroup(
    "admin",
    "Bot administration commands",
    guild_ids=settings.guild_ids,
)


class AdminCog(commands.Cog):
    """Admin commands placeholder cog.

    This cog doesn't define any commands directly - it just ensures the
    /admin group is registered. Subcommands are added by other cogs
    via admin.create_subgroup().
    """

    def __init__(self, bot: Bot):
        self.bot = bot


def setup(bot: Bot) -> None:
    """Load the AdminCog and register the admin command group."""
    cog = AdminCog(bot)
    bot.add_cog(cog)
    # Register the admin group at module level so other cogs can add subgroups
    bot.add_application_command(admin)
