import logging

from discord import Member, Message, User, Embed
from discord.ext import commands
from sqlalchemy import select

from src.bot import Bot
from src.database.models import HtbDiscordLink
from src.database.session import AsyncSessionLocal
from src.helpers.verification import get_user_details, process_identification
from src.core import settings

logger = logging.getLogger(__name__)


class CommandLog(commands.Cog):
    """Cog for handling verification automatically."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def on_command(self, ctx: Message) -> None:
        """Called when a command is run"""
        embed=Embed(title="Command Log")
        embed.add_field(name="Command", value=ctx.command, inline=True)
        embed.add_field(name="Caller", value=ctx.author.name, inline=True)
        embed.add_field(name="Channel", value=ctx.channel.name, inline=True)
        await ctx.guild.get_channel(settings.channels.BOT_LOGS).send(embed=embed)


def setup(bot: Bot) -> None:
    """Load the `CommandLog` cog."""
    bot.add_cog(CommandLog(bot))
