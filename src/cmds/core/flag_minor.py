"""Flag verified users as potentially underage for review."""

import logging
from datetime import datetime, timezone

import discord
from discord import ApplicationContext, WebhookMessage
from discord.ext.commands import has_any_role

from src.bot import Bot
from src.core import settings
from src.database.models import MinorReport
from src.database.session import AsyncSessionLocal
from src.helpers.minor_verification import (
    PENDING,
    assign_minor_role,
    check_parental_consent,
    get_account_identifier_for_discord,
    get_active_minor_report,
    get_htb_user_id_for_discord,
    years_until_18,
)
from src.views.minorreportview import HTB_PROFILE_URL, MinorReportView, build_minor_report_embed

logger = logging.getLogger(__name__)


class FlagMinorCog(discord.Cog):
    """Commands for flagging potentially underage users."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @discord.slash_command(
        guild_ids=settings.guild_ids,
        description="Flag a verified user as potentially underage for review.",
    )
    @has_any_role(
        *settings.role_groups.get("ALL_ADMINS"),
        *settings.role_groups.get("ALL_MODS"),
    )
    async def flag_minor(
        self,
        ctx: ApplicationContext,
        user: discord.Member,
        suspected_age: int,
        evidence: str,
    ) -> ApplicationContext | WebhookMessage:
        """Flag a verified user as potentially underage. Only MOD+ can use this."""
        if not ctx.guild:
            return await ctx.respond("This command can only be used in a server.", ephemeral=True)

        if suspected_age < 1 or suspected_age > 17:
            return await ctx.respond(
                "Suspected age must be between 1 and 17.",
                ephemeral=True,
            )

        verified_role_id = settings.roles.VERIFIED
        minor_role_id = getattr(settings.roles, "VERIFIED_MINOR", None)
        if not minor_role_id:
            return await ctx.respond(
                "Minor review is not configured (VERIFIED_MINOR role missing).",
                ephemeral=True,
            )

        verified_role = ctx.guild.get_role(verified_role_id)
        minor_role = ctx.guild.get_role(minor_role_id)
        if not verified_role or not minor_role:
            return await ctx.respond(
                "Required roles are not configured on this server.",
                ephemeral=True,
            )

        target = await self.bot.get_member_or_user(ctx.guild, user.id)
        if not target:
            return await ctx.respond("User not found.", ephemeral=True)

        if not isinstance(target, discord.Member):
            return await ctx.respond(
                "User must be a member of this server and have the Verified role.",
                ephemeral=True,
            )

        if verified_role not in target.roles:
            return await ctx.respond(
                "That user is not verified. Only verified users can be flagged.",
                ephemeral=True,
            )

        if minor_role in target.roles:
            return await ctx.respond(
                "That user already has the verified-minor status. No need to flag.",
                ephemeral=True,
            )

        status_message = await ctx.respond(
            "Creating or updating minor report, please wait...",
            ephemeral=True,
        )

        account_identifier = await get_account_identifier_for_discord(target.id)
        if not account_identifier:
            await status_message.edit(
                content="Could not find linked HTB account for this user. They must be verified first.",
            )
            return

        has_consent = await check_parental_consent(account_identifier)
        if has_consent:
            added = await assign_minor_role(target, ctx.guild)
            await status_message.edit(
                content=(
                    "Parental consent already on file. No report created."
                    + (" Role assigned." if added else " Role was already assigned.")
                ),
            )
            return

        review_channel_id = getattr(settings.channels, "MINOR_REVIEW", None) or 0
        if not review_channel_id:
            await status_message.edit(
                content="Minor review channel is not configured. Report could not be created.",
            )
            return

        review_channel = ctx.guild.get_channel(review_channel_id)
        if not review_channel:
            await status_message.edit(
                content="Minor review channel not found. Report could not be created.",
            )
            return

        now = datetime.now(timezone.utc)
        existing = await get_active_minor_report(target.id)

        if existing:
            async with AsyncSessionLocal() as session:
                r = await session.get(MinorReport, existing.id)
                if r:
                    r.suspected_age = suspected_age
                    r.evidence = evidence
                    r.reporter_id = ctx.user.id
                    r.updated_at = now
                    await session.commit()
                    report = r
                else:
                    report = existing
            htb_id = await get_htb_user_id_for_discord(target.id)
            htb_url = f"{HTB_PROFILE_URL}{htb_id}" if htb_id else None
            embed = build_minor_report_embed(
                report,
                ctx.guild,
                reported_user=target,
                status_notes=f"Report updated by <@{ctx.user.id}>.",
                htb_profile_url=htb_url,
            )
            try:
                msg = await review_channel.fetch_message(report.report_message_id)
                await msg.edit(embed=embed)
            except (discord.NotFound, discord.HTTPException) as e:
                logger.warning("Could not edit existing report message: %s", e)
            await status_message.edit(
                content="Report updated with new information. Review channel message edited.",
            )
            return

        view = MinorReportView(self.bot)
        embed = discord.Embed(
            title=f"Minor Report - {PENDING}",
            color=0xFFA500,
        )
        embed.add_field(
            name="User",
            value=f"<@{target.id}> ({target.id})",
            inline=False,
        )
        embed.add_field(name="Suspected Age", value=str(suspected_age), inline=True)
        embed.add_field(
            name="Suggested Ban Duration",
            value=f"{years_until_18(suspected_age)} years (until 18)",
            inline=True,
        )
        embed.add_field(name="Evidence", value=evidence or "—", inline=False)
        embed.add_field(name="Flagged By", value=f"<@{ctx.user.id}>", inline=True)
        embed.add_field(name="Flagged At", value=now.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
        if target.display_avatar.url:
            embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="Report pending | Last updated: " + now.strftime("%Y-%m-%d %H:%M UTC"))

        sent = await review_channel.send(embed=embed, view=view)
        report = MinorReport(
            user_id=target.id,
            reporter_id=ctx.user.id,
            suspected_age=suspected_age,
            evidence=evidence,
            report_message_id=sent.id,
            status=PENDING,
            created_at=now,
            updated_at=now,
        )
        async with AsyncSessionLocal() as session:
            session.add(report)
            await session.commit()
            await session.refresh(report)

        htb_id = await get_htb_user_id_for_discord(target.id)
        htb_url = f"{HTB_PROFILE_URL}{htb_id}" if htb_id else None
        embed_with_id = build_minor_report_embed(
            report,
            ctx.guild,
            reported_user=target,
            htb_profile_url=htb_url,
        )
        embed_with_id.set_footer(
            text=f"Report ID: {report.id} | Last updated: {report.updated_at.strftime('%Y-%m-%d %H:%M UTC')}"
        )
        await sent.edit(embed=embed_with_id)

        await status_message.edit(
            content=(
                "Report created and posted to the review channel."
            ),
        )
        return

    @discord.Cog.listener()
    async def on_ready(self) -> None:
        """Register persistent view when bot is ready."""
        self.bot.add_view(MinorReportView(self.bot))


def setup(bot: Bot) -> None:
    """Load the FlagMinorCog."""
    bot.add_cog(FlagMinorCog(bot))
