import logging

from discord import Member, Message, User
from discord.ext import commands

from src.bot import Bot

logger = logging.getLogger(__name__)


class MessageHandler(commands.Cog):
    """Cog for handling verification automatically."""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def process_reverification(self, member: Member | User) -> None:
        """Re-verifation process for a member.
        
        TODO: Reimplement once it's possible to fetch link state from the HTB Account.
        """
        raise VerificationError("Not implemented")

    @commands.Cog.listener()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def on_message(self, ctx: Message) -> None:
        """Run commands in the context of a message."""
        # Return if the message was sent by the bot to avoid recursion.
        if ctx.author.bot:
            return
        # When a user types in un-verified-bot-commands, hold their hand in finding the how-to-talk channel so they can verify.
        if ctx.channel.id == 1430556712313688225:
            await ctx.reply(
                "Hello! Welcome to the Hack The Box Discord! In-order to access the full server, please verify your account by following the instructions in <#1432333413980835840>.",
                mention_author=True,
            )
        try:
            await self.process_reverification(ctx.author)
        except VerificationError as exc:
            logger.debug(f"HTB Discord link for user {ctx.author.name} with ID {ctx.author.id} not found", exc_info=exc)

    @commands.Cog.listener()
    @commands.cooldown(1, 3600, commands.BucketType.user)
    async def on_member_join(self, member: Member) -> None:
        """Run commands in the context of a member join."""
        try:
            await self.process_reverification(member)
        except VerificationError as exc:
            logger.debug(f"HTB Discord link for user {member.name} with ID {member.id} not found", exc_info=exc)


class VerificationError(Exception):
    """Verification error."""


def setup(bot: Bot) -> None:
    """Load the `MessageHandler` cog."""
    # bot.add_cog(MessageHandler(bot))
    pass
