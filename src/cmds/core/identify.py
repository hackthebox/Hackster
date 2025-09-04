import logging

from discord import ApplicationContext, Interaction, WebhookMessage, slash_command
from discord.ext import commands
from discord.ext.commands import cooldown

from src.bot import Bot
from src.core import settings
from src.helpers.verification import send_verification_instructions

logger = logging.getLogger(__name__)


class IdentifyCog(commands.Cog):
    """Identify discord member with HTB."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @slash_command(
        guild_ids=settings.guild_ids,
        description="Identify yourself on the HTB Discord server by linking your HTB account ID to your Discord user "
        "ID.",
        guild_only=False,
    )
    @cooldown(1, 60, commands.BucketType.user)
    async def identify(
        self, ctx: ApplicationContext, account_identifier: str
    ) -> Interaction | WebhookMessage:
        """Legacy command. Now sends instructions to identify with HTB account."""
        await send_verification_instructions(ctx, ctx.author)


def setup(bot: Bot) -> None:
    """Load the `IdentifyCog` cog."""
    bot.add_cog(IdentifyCog(bot))
