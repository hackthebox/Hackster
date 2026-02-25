"""View and embed builder for minor reports in the review channel."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord import Guild, HTTPException, Interaction, Member, NotFound, User
from discord.ui import Button, InputText, Modal, View
from sqlalchemy import select

from src.bot import Bot
from src.core import settings  # noqa: F401
from src.database.models import Ban, MinorReport, UserNote
from src.database.session import AsyncSessionLocal
from src.helpers.ban import ban_member_with_epoch, get_ban, unban_member
from src.helpers.minor_verification import (
    APPROVED,
    CONSENT_VERIFIED,
    DENIED,
    PENDING,
    assign_minor_role,
    check_parental_consent,
    get_account_identifier_for_discord,
    get_htb_user_id_for_discord,
    is_minor_review_moderator,
    years_until_18,
)

logger = logging.getLogger(__name__)

HTB_PROFILE_URL = "https://app.hackthebox.com/users/"

# Button custom_ids - we look up report by message_id
CUSTOM_ID_APPROVE = "minor_report_approve"
CUSTOM_ID_DENY = "minor_report_deny"
CUSTOM_ID_RECHECK = "minor_report_recheck"


def _status_color(status: str) -> int:
    if status == PENDING:
        return 0xFFA500  # Orange
    if status == APPROVED:
        return 0xFF2429  # Red
    if status == DENIED:
        return 0x00FF00  # Green
    if status == CONSENT_VERIFIED:
        return 0x0099FF  # Blue
    return 0x808080


def build_minor_report_embed(
    report: MinorReport,
    guild: Guild,
    *,
    reported_user: Member | User | None = None,
    status_notes: str = "",
    htb_profile_url: str | None = None,
) -> discord.Embed:
    """Build the embed for a minor report message."""
    status = report.status
    title = f"Minor Report #{report.id} - {status.upper().replace('_', ' ')}"
    embed = discord.Embed(title=title, color=_status_color(status))

    user_mention = f"<@{report.user_id}>"
    embed.add_field(name="User", value=f"{user_mention} ({report.user_id})", inline=False)
    if htb_profile_url:
        embed.add_field(
            name="HTB Profile",
            value=f"[View profile]({htb_profile_url})",
            inline=False,
        )

    embed.add_field(name="Suspected Age", value=str(report.suspected_age), inline=True)
    years = years_until_18(report.suspected_age)
    embed.add_field(
        name="Suggested Ban Duration",
        value=f"{years} years (until 18)",
        inline=True,
    )
    embed.add_field(name="Evidence", value=report.evidence or "—", inline=False)
    embed.add_field(name="Flagged By", value=f"<@{report.reporter_id}>", inline=True)
    created = report.created_at
    if isinstance(created, datetime):
        created_str = created.strftime("%Y-%m-%d %H:%M UTC")
    else:
        created_str = str(created)
    embed.add_field(name="Flagged At", value=created_str, inline=True)
    if status_notes:
        embed.add_field(name="Status Updates", value=status_notes, inline=False)
    if reported_user and reported_user.display_avatar.url:
        embed.set_thumbnail(url=reported_user.display_avatar.url)
    updated = report.updated_at
    updated_str = updated.strftime("%Y-%m-%d %H:%M UTC") if isinstance(updated, datetime) else str(updated)
    embed.set_footer(text=f"Report ID: {report.id} | Last updated: {updated_str}")

    return embed


async def get_report_by_message_id(message_id: int) -> MinorReport | None:
    """Load MinorReport by report_message_id."""
    async with AsyncSessionLocal() as session:
        stmt = select(MinorReport).filter(MinorReport.report_message_id == message_id).limit(1)
        result = await session.scalars(stmt)
        return result.first()


async def update_report_status(
    report_id: int,
    status: str,
    reviewer_id: int,
    *,
    associated_ban_id: int | None = None,
) -> None:
    """Update report status and updated_at."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        report = await session.get(MinorReport, report_id)
        if report:
            report.status = status
            report.reviewer_id = reviewer_id
            report.updated_at = now
            if associated_ban_id is not None:
                report.associated_ban_id = associated_ban_id
            await session.commit()


# Modal for approving ban (confirm/adjust duration)
class ApproveBanModal(Modal):
    """Modal to confirm or adjust ban duration when approving a minor report."""

    def __init__(self, bot: Bot, report: MinorReport, parent_view: MinorReportView):
        super().__init__(title="Approve Ban")
        self.bot = bot
        self.report = report
        self.parent_view = parent_view
        years = years_until_18(report.suspected_age)
        default_duration = f"{years}y"
        self.add_item(
            InputText(
                label="Ban duration",
                placeholder="e.g. 5y or 3y",
                required=True,
                value=default_duration,
            )
        )

    async def callback(self, interaction: Interaction) -> None:
        """Validate duration, create ban, update report and embed."""
        from src.helpers.duration import validate_duration
        duration_str = self.children[0].value.strip()
        dur, dur_exc = validate_duration(duration_str)
        if dur_exc or dur <= 0:
            await interaction.response.send_message(
                dur_exc or "Invalid duration.",
                ephemeral=True,
            )
            return
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Guild not found.", ephemeral=True)
            return
        member = await self.bot.get_member_or_user(guild, self.report.user_id)
        if not member:
            await interaction.response.send_message("User not found in guild.", ephemeral=True)
            return
        reason = (
            "Parental consent is missing. Please submit parental consent after reviewing the article: "
            "https://help.hackthebox.com/en/articles/9456556-parental-consent-and-approval-for-users-under-18"
        )
        end_date = datetime.fromtimestamp(dur, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        response = await ban_member_with_epoch(
            self.bot,
            guild,
            member,
            dur,
            reason,
            f"Minor report approval by {interaction.user.mention} ({interaction.user.id})",
            author=interaction.user,
            needs_approval=True,
        )
        # Get the ban id we just created
        async with AsyncSessionLocal() as session:
            stmt = select(Ban).filter(Ban.user_id == member.id).order_by(Ban.id.desc()).limit(1)
            result = await session.scalars(stmt)
            ban = result.first()
            ban_id = ban.id if ban else None
        await update_report_status(
            self.report.id,
            APPROVED,
            interaction.user.id,
            associated_ban_id=ban_id,
        )
        await interaction.response.send_message(
            response.message or f"Ban submitted until {end_date} (UTC). Awaiting SR_MOD approval.",
            ephemeral=True,
        )
        status_notes = f"Approved by <@{interaction.user.id}> at <t:{int(datetime.now(timezone.utc).timestamp())}:F>"
        report_for_embed = await get_report_by_message_id(interaction.message.id) or self.report
        htb_id = await get_htb_user_id_for_discord(report_for_embed.user_id)
        htb_url = f"{HTB_PROFILE_URL}{htb_id}" if htb_id else None
        embed = build_minor_report_embed(
            report_for_embed,
            guild,
            reported_user=member,
            status_notes=status_notes,
            htb_profile_url=htb_url,
        )
        # After approval, disable further approval/denial on this message and
        # change the recheck button label for this report only so reviewers
        # clearly see that it will check consent and unban.
        for child in self.parent_view.children:
            if isinstance(child, _ApproveButton) or isinstance(child, _DenyButton):
                child.disabled = True
            if isinstance(child, _RecheckButton):
                child.label = "Check Consent & Unban"
        # Keep the view so reviewers can later recheck consent and unban if needed.
        await self.parent_view._edit_report_message(interaction, embed, view=self.parent_view)


class DenyReportModal(Modal):
    """Modal to enter denial reason when denying a minor report."""

    def __init__(self, bot: Bot, report: MinorReport, parent_view: MinorReportView):
        super().__init__(title="Deny Report")
        self.bot = bot
        self.report = report
        self.parent_view = parent_view
        self.add_item(
            InputText(
                label="Reason for denial",
                placeholder="Brief reason",
                required=True,
            )
        )

    async def callback(self, interaction: Interaction) -> None:
        """Save denial reason, add user note, update report embed."""
        reason = self.children[0].value.strip() or "No reason given"
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Guild not found.", ephemeral=True)
            return
        await update_report_status(self.report.id, DENIED, interaction.user.id)
        note_text = f"Minor flag denied: {reason}"
        today = datetime.now(timezone.utc).date()
        user_note = UserNote(
            user_id=self.report.user_id,
            note=note_text,
            moderator_id=interaction.user.id,
            date=today,
        )
        async with AsyncSessionLocal() as session:
            session.add(user_note)
            await session.commit()
        await interaction.response.send_message(
            "Report denied and note added to user history.",
            ephemeral=True,
        )
        ts = int(datetime.now(timezone.utc).timestamp())
        status_notes = f"Denied by <@{interaction.user.id}> at <t:{ts}:F>. Reason: {reason}"
        report_updated = await get_report_by_message_id(interaction.message.id)
        report_for_embed = report_updated or self.report
        htb_id = await get_htb_user_id_for_discord(report_for_embed.user_id)
        htb_url = f"{HTB_PROFILE_URL}{htb_id}" if htb_id else None
        embed = build_minor_report_embed(
            report_for_embed,
            guild,
            status_notes=status_notes,
            htb_profile_url=htb_url,
        )
        try:
            await interaction.message.edit(embed=embed, view=None)
        except (HTTPException, NotFound):
            pass


class _ApproveButton(Button):
    def __init__(self):
        super().__init__(label="Approve Ban", style=discord.ButtonStyle.success, custom_id=CUSTOM_ID_APPROVE)

    async def callback(self, interaction: Interaction) -> None:
        view: MinorReportView = self.view
        report = await view._get_report(interaction)
        if report and report.status == PENDING:
            await view._approve_callback(interaction, report)
        elif report:
            await interaction.response.send_message("This report is no longer pending.", ephemeral=True)


class _DenyButton(Button):
    def __init__(self):
        super().__init__(label="Deny Report", style=discord.ButtonStyle.danger, custom_id=CUSTOM_ID_DENY)

    async def callback(self, interaction: Interaction) -> None:
        view: MinorReportView = self.view
        report = await view._get_report(interaction)
        if report and report.status == PENDING:
            await view._deny_callback(interaction, report)
        elif report:
            await interaction.response.send_message("This report is no longer pending.", ephemeral=True)


class _RecheckButton(Button):
    def __init__(self):
        # Default label for newly created (pending) reports.
        super().__init__(label="Recheck Consent", style=discord.ButtonStyle.primary, custom_id=CUSTOM_ID_RECHECK)

    async def callback(self, interaction: Interaction) -> None:
        view: MinorReportView = self.view
        report = await view._get_report(interaction)
        if report:
            await view._recheck_callback(interaction, report)


class MinorReportView(View):
    """Persistent view for minor report actions. Look up report by message_id."""

    def __init__(self, bot: Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(_ApproveButton())
        self.add_item(_DenyButton())
        self.add_item(_RecheckButton())

    async def _get_report(self, interaction: Interaction) -> MinorReport | None:
        return await get_report_by_message_id(interaction.message.id)

    async def _check_reviewer(self, interaction: Interaction) -> bool:
        if not await is_minor_review_moderator(interaction.user.id):
            await interaction.response.send_message(
                "You are not authorized to review minor reports.",
                ephemeral=True,
            )
            return False
        return True

    async def interaction_check(self, interaction: Interaction) -> bool:
        """Ensure report exists and user is an allowed reviewer."""
        report = await self._get_report(interaction)
        if not report:
            await interaction.response.send_message(
                "Report not found or already resolved.",
                ephemeral=True,
            )
            return False
        return await self._check_reviewer(interaction)

    @staticmethod
    async def _edit_report_message(interaction: Interaction, embed: discord.Embed, view: View | None = None) -> None:
        """Edit the report message with updated embed and optional view."""
        try:
            await interaction.message.edit(embed=embed, view=view)
        except (HTTPException, NotFound) as e:
            logger.warning("Failed to edit minor report message: %s", e)

    async def _approve_callback(self, interaction: Interaction, report: MinorReport) -> None:
        modal = ApproveBanModal(self.bot, report, self)
        await interaction.response.send_modal(modal)

    async def _deny_callback(self, interaction: Interaction, report: MinorReport) -> None:
        modal = DenyReportModal(self.bot, report, self)
        await interaction.response.send_modal(modal)

    async def _recheck_callback(self, interaction: Interaction, report: MinorReport) -> None:
        await interaction.response.defer(ephemeral=True)
        account_id = await get_account_identifier_for_discord(report.user_id)
        if not account_id:
            await interaction.followup.send(
                "Could not find linked account for this user.",
                ephemeral=True,
            )
            return
        has_consent = await check_parental_consent(account_id)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("Guild not found.", ephemeral=True)
            return
        member = await self.bot.get_member_or_user(guild, report.user_id)
        if has_consent:
            # Try to assign the minor role only if we have a real Member object.
            if isinstance(member, Member):
                await assign_minor_role(member, guild)
            existing_ban = await get_ban(member) if member else await get_ban(discord.Object(id=report.user_id))
            if existing_ban and report.associated_ban_id and existing_ban.id == report.associated_ban_id:
                # Unban by member if present, otherwise by user id.
                if member:
                    await unban_member(guild, member)
                else:
                    await unban_member(guild, discord.Object(id=report.user_id))
                await interaction.followup.send(
                    "Consent found. User unbanned."
                    + (" Minor role assigned." if isinstance(member, Member) else " Minor role will be assigned when they rejoin."),
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "Consent found."
                    + (" Minor role assigned." if isinstance(member, Member) else " Minor role will be assigned when they rejoin.")
                    + (" User was not banned by this report." if not existing_ban else ""),
                    ephemeral=True,
                )
            await update_report_status(report.id, CONSENT_VERIFIED, interaction.user.id)
            status_notes = (
                f"Consent verified by <@{interaction.user.id}> at "
                f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>"
            )
        else:
            await interaction.followup.send(
                "Consent still not found. No changes made.",
                ephemeral=True,
            )
            status_notes = (
                f"Recheck (no consent) by <@{interaction.user.id}> at "
                f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>"
            )

        # Persist updated status/reviewer/timestamp
        if has_consent:
            report.status = CONSENT_VERIFIED
        report.reviewer_id = interaction.user.id
        report.updated_at = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            r = await session.get(MinorReport, report.id)
            if r:
                r.status = report.status
                r.reviewer_id = report.reviewer_id
                r.updated_at = report.updated_at
                await session.commit()
        report_for_embed = r or report
        htb_id = await get_htb_user_id_for_discord(report_for_embed.user_id)
        htb_url = f"{HTB_PROFILE_URL}{htb_id}" if htb_id else None
        embed = build_minor_report_embed(
            report_for_embed,
            guild,
            reported_user=member,
            status_notes=status_notes,
            htb_profile_url=htb_url,
        )
        # If consent is found, this is a terminal state: remove all buttons.
        # Otherwise, keep the existing view so reviewers can try rechecking again.
        view = None if has_consent else self
        await self._edit_report_message(interaction, embed, view)
