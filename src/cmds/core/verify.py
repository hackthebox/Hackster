import logging

from discord import ApplicationContext, Interaction, WebhookMessage, slash_command
from discord.ext import commands
from discord.ext.commands import cooldown

from src.bot import Bot
from src.core import settings
from src.helpers.verification import process_certification, send_verification_instructions

logger = logging.getLogger(__name__)


class VerifyCog(commands.Cog):
    """Verify discord member with HTB."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @slash_command(
        guild_ids=settings.guild_ids,
        description="Verify your HTB Certifications!"
    )
    @cooldown(1, 60, commands.BucketType.user)
    async def verifycertification(self, ctx: ApplicationContext, certid: str, fullname: str) -> Interaction | WebhookMessage | None:
        """Verify users their HTB Certification."""
        if not certid or not fullname:
            await ctx.respond("You must supply a cert id!", ephemeral=True)
            return
        if not certid.startswith("HTBCERT-"):
            await ctx.respond("CertID must start with HTBCERT-", ephemeral=True)
            return
        cert = await process_certification(certid, fullname)
        if cert:
            to_add = settings.get_cert(cert)
            await ctx.author.add_roles(ctx.guild.get_role(to_add))
            await ctx.respond(f"Added {cert}!", ephemeral=True)
        else:
            await ctx.respond("Unable to find certification with provided details", ephemeral=True)

    @slash_command(
        guild_ids=settings.guild_ids,
        description="Receive instructions in a DM on how to identify yourself with your HTB account."
    )
    @cooldown(1, 60, commands.BucketType.user)
    async def verify(self, ctx: ApplicationContext) -> Interaction | WebhookMessage:
        """Receive instructions in a DM on how to identify yourself with your HTB account."""
        await send_verification_instructions(ctx, ctx.author)


def setup(bot: Bot) -> None:
    """Load the `VerifyCog` cog."""
    bot.add_cog(VerifyCog(bot))
