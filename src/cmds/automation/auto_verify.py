import logging

from discord import Member, Message, User
from discord.ext import commands
from sqlalchemy import select

from src.bot import Bot
from src.database.models import HtbDiscordLink
from src.database.session import AsyncSessionLocal
from src.helpers.verification import get_user_details, process_identification

logger = logging.getLogger(__name__)


class MessageHandler(commands.Cog):
    """Cog for handling verification automatically."""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def process_reverification(self, member: Member | User) -> None:
        """Re-verifation process for a member."""
        async with AsyncSessionLocal() as session:
            stmt = (
                select(HtbDiscordLink)
                .where(HtbDiscordLink.discord_user_id == member.id)
                .order_by(HtbDiscordLink.id)
                .limit(1)
            )
            result = await session.scalars(stmt)
            htb_discord_link: HtbDiscordLink = result.first()

        if not htb_discord_link:
            raise VerificationError(f"HTB Discord link for user {member.name} with ID {member}")

        member_token: str = htb_discord_link.account_identifier

        if member_token is None:
            raise VerificationError(f"HTB account identifier for user {member.name} with ID {member.id} not found")

        logger.debug(f"Processing re-verify of member {member.name} ({member.id}).")
        htb_details = await get_user_details(member_token)
        if htb_details is None:
            raise VerificationError(f"Retrieving user details for user {member.name} with ID {member.id} failed")

        await process_identification(htb_details, user=member, bot=self.bot)

    @commands.Cog.listener()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def on_message(self, ctx: Message) -> None:
        """Run commands in the context of a message."""
        # Return if the message was sent by the bot to avoid recursion.
        if ctx.author.bot:
            return

        try:
            await self.process_reverification(ctx.author)
        except VerificationError as exc:
            logger.debug(
                f"HTB Discord link for user {ctx.author.name} with ID {ctx.author.id} not found", exc_info=exc
            )

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
    bot.add_cog(MessageHandler(bot))
