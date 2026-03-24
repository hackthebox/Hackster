import logging

from discord import Member, Message, User
from discord.ext import commands

from src.bot import Bot
from src.core.config import settings

logger = logging.getLogger(__name__)


class MessageHandler(commands.Cog):
    """Cog for handling verification automatically."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def on_message(self, ctx: Message) -> None:
        """Guide unverified users toward the verification channel."""
        if ctx.author.bot:
            return

        if ctx.channel.id == settings.channels.UNVERIFIED_BOT_COMMANDS:
            await ctx.reply(
                f"Hello! Welcome to the Hack The Box Discord! In order to access the full server, "
                f"please verify your account by following the instructions in "
                f"<#{settings.channels.HOW_TO_VERIFY}>.",
                mention_author=True,
            )
            return

    @commands.Cog.listener()
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def on_member_join(self, member: Member) -> None:
        """Run commands in the context of a member join."""
        pass


def setup(bot: Bot) -> None:
    """Load the `MessageHandler` cog."""
    bot.add_cog(MessageHandler(bot))
