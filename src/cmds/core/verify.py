import logging

import discord
from discord import ApplicationContext, Interaction, WebhookMessage, slash_command
from discord.errors import Forbidden, HTTPException
from discord.ext import commands
from discord.ext.commands import cooldown

from src.bot import Bot
from src.core import settings
from src.helpers.verification import process_certification
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
    async def verifycertification(self, ctx: ApplicationContext, certid: str, fullname: str) -> Interaction | WebhookMessage:
        if not certid or not fullname:
            await ctx.respond("You must supply a cert id!", ephemeral=True)
            return
        if not certid.startswith("HTBCERT-"):
            await ctx.respond("CertID must start with HTBCERT-", ephemeral=True)
            return
        cert = process_certification(certid, fullname)
        if cert:
            toAdd = settings.get_cert(cert)
            await ctx.author.add_roles(toAdd)
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
        member = ctx.user

        # Step one
        embed_step1 = discord.Embed(color=0x9ACC14)
        embed_step1.add_field(
            name="Step 1: Log in at Hack The Box",
            value="Log in to your Hack The Box account at <https://www.hackthebox.com/> and navigate to the settings "
                  "page.", inline=False, )
        embed_step1.set_image(
            url="https://media.discordapp.net/attachments/724587782755844098/839871275627315250/unknown.png"
        )

        # Step two
        embed_step2 = discord.Embed(color=0x9ACC14)
        embed_step2.add_field(
            name="Step 2: Locate the Account Identifier",
            value='In the settings tab, look for a field called "Account Identifier". Next, click the green button to '
                  "copy your secret identifier.", inline=False, )
        embed_step2.set_image(
            url="https://media.discordapp.net/attachments/724587782755844098/839871332963188766/unknown.png"
        )

        # Step three
        embed_step3 = discord.Embed(color=0x9ACC14)
        embed_step3.add_field(
            name="Step 3: Identification",
            value="Now type `/identify IDENTIFIER_HERE` in the bot-commands channel.\n\nYour roles will then be "
                  "automatically applied.", inline=False
        )
        embed_step3.set_image(
            url="https://media.discordapp.net/attachments/709907130102317093/904744444539076618/unknown.png"
        )

        try:
            await member.send(embed=embed_step1)
            await member.send(embed=embed_step2)
            await member.send(embed=embed_step3)
        except Forbidden as ex:
            logger.error("Exception during verify call", exc_info=ex)
            return await ctx.respond(
                "Whoops! I cannot DM you after all due to your privacy settings. Please allow DMs from other server "
                "members and try again in 1 minute."
            )
        except HTTPException as ex:
            logger.error("Exception during verify call.", exc_info=ex)
            return await ctx.respond(
                "An unexpected error happened (HTTP 400, bad request). Please contact an Administrator."
            )
        return await ctx.respond("Please check your DM for instructions.", ephemeral=True)


def setup(bot: Bot) -> None:
    """Load the `VerifyCog` cog."""
    bot.add_cog(VerifyCog(bot))
