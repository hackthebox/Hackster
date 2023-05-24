import logging
from typing import Sequence

import discord
from discord import ApplicationContext, Interaction, WebhookMessage, slash_command
from discord.ext import commands
from discord.ext.commands import cooldown
from sqlalchemy import select

from src.bot import Bot
from src.core import settings
from src.database.models import HtbDiscordLink
from src.database.session import AsyncSessionLocal
from src.helpers.verification import get_user_details, process_identification

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
    async def identify(self, ctx: ApplicationContext, account_identifier: str) -> Interaction | WebhookMessage:
        """Identify yourself on the HTB Discord server by linking your HTB account ID to your Discord user ID."""
        if len(account_identifier) != 60:
            return await ctx.respond(
                "This Account Identifier does not appear to be the right length (must be 60 characters long).",
                ephemeral=True,
            )

        await ctx.respond("Identification initiated, please wait...", ephemeral=True)
        htb_user_details = await get_user_details(account_identifier)
        if htb_user_details is None:
            embed = discord.Embed(title="Error: Invalid account identifier.", color=0xFF0000)
            return await ctx.respond(embed=embed, ephemeral=True)

        json_htb_user_id = htb_user_details["user_id"]

        author = ctx.user
        member = await self.bot.get_or_fetch_user(author.id)
        if not member:
            return await ctx.respond(f"Error getting guild member with id: {author.id}.")

        # Step 1: Check if the Account Identifier has already been recorded and if they are the previous owner.
        # Scenario:
        #   - I create a new Discord account.
        #   - I reuse my previous Account Identifier.
        #   - I now have an "alt account" with the same roles.
        async with AsyncSessionLocal() as session:
            stmt = (
                select(HtbDiscordLink)
                .filter(HtbDiscordLink.account_identifier == account_identifier)
                .order_by(HtbDiscordLink.id.desc())
                .limit(1)
            )
            result = await session.scalars(stmt)
            most_recent_rec: HtbDiscordLink = result.first()

        if most_recent_rec and most_recent_rec.discord_user_id_as_int != member.id:
            error_desc = (
                f"Verified user {member.mention} tried to identify as another identified user.\n"
                f"Current Discord UID: {member.id}\n"
                f"Other Discord UID: {most_recent_rec.discord_user_id}\n"
                f"Related HTB UID: {most_recent_rec.htb_user_id}"
            )
            embed = discord.Embed(title="Identification error", description=error_desc, color=0xFF2429)
            await self.bot.get_channel(settings.channels.BOT_LOGS).send(embed=embed)

            return await ctx.respond(
                "Identification error: please contact an online Moderator or Administrator for help.", ephemeral=True
            )

        # Step 2: Given the htb_user_id from JSON, check if each discord_user_id are different from member.id.
        # Scenario:
        #   - I have a Discord account that is linked already to a "Hacker" role.
        #   - I create a new HTB account.
        #   - I identify with the new account.
        #   - `SELECT * FROM htb_discord_link WHERE htb_user_id = %s` will be empty,
        #         because the new account has not been verified before. All is good.
        #   - I am now "Noob" rank.
        async with AsyncSessionLocal() as session:
            stmt = select(HtbDiscordLink).filter(HtbDiscordLink.htb_user_id == json_htb_user_id)
            result = await session.scalars(stmt)
            user_links: Sequence[HtbDiscordLink] = result.all()

        discord_user_ids = {u_link.discord_user_id_as_int for u_link in user_links}
        if discord_user_ids and member.id not in discord_user_ids:
            orig_discord_ids = ", ".join([f"<@{id_}>" for id_ in discord_user_ids])
            error_desc = (
                f"The HTB account {json_htb_user_id} attempted to be identified by user <@{member.id}>, "
                f"but is tied to another Discord account.\n"
                f"Originally linked to Discord UID {orig_discord_ids}."
            )
            embed = discord.Embed(title="Identification error", description=error_desc, color=0xFF2429)
            await self.bot.get_channel(settings.channels.BOT_LOGS).send(embed=embed)

            return await ctx.respond(
                "Identification error: please contact an online Moderator or Administrator for help.", ephemeral=True
            )

        # Step 3: Check if discord_user_id already linked to an htb_user_id, and if JSON/db HTB IDs are the same.
        # Scenario:
        #   - I have a new, unlinked Discord account.
        #   - Clubby generates a new token and gives it to me.
        #   - `SELECT * FROM htb_discord_link WHERE discord_user_id = %s`
        #         will be empty because I have not identified before.
        #   - I am now Clubby.
        async with AsyncSessionLocal() as session:
            stmt = select(HtbDiscordLink).filter(HtbDiscordLink.discord_user_id == member.id)
            result = await session.scalars(stmt)
            user_links: Sequence[HtbDiscordLink] = result.all()

        user_htb_ids = {u_link.htb_user_id_as_int for u_link in user_links}
        if user_htb_ids and json_htb_user_id not in user_htb_ids:
            error_desc = (
                f"User {member.mention} ({member.id}) tried to identify with a new HTB account.\n"
                f"Original HTB UIDs: {', '.join([str(i) for i in user_htb_ids])}, new HTB UID: "
                f"{json_htb_user_id}."
            )
            embed = discord.Embed(title="Identification error", description=error_desc, color=0xFF2429)
            await self.bot.get_channel(settings.channels.BOT_LOGS).send(embed=embed)

            return await ctx.respond(
                "Identification error: please contact an online Moderator or Administrator for help.", ephemeral=True
            )

        htb_discord_link = HtbDiscordLink(
            account_identifier=account_identifier, discord_user_id=member.id, htb_user_id=json_htb_user_id
        )
        async with AsyncSessionLocal() as session:
            session.add(htb_discord_link)
            await session.commit()

        await process_identification(htb_user_details, user=member, bot=self.bot)

        return await ctx.respond(
            f"Your Discord user has been successfully identified as HTB user {json_htb_user_id}.", ephemeral=True
        )


def setup(bot: Bot) -> None:
    """Load the `IdentifyCog` cog."""
    bot.add_cog(IdentifyCog(bot))
