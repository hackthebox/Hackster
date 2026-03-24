import logging
from datetime import datetime

import discord
from discord import Interaction
from discord.ui import Button, InputText, Modal, View
from sqlalchemy import select

from src.bot import Bot
from src.core import settings
from src.database.models import Ban
from src.database.session import AsyncSessionLocal
from src.helpers.duration import validate_duration
from src.helpers.schedule import schedule

logger = logging.getLogger(__name__)


class BanDecisionView(View):
    """Persistent view for making decisions on a ban duration.

    Encodes the ban_id into each button's custom_id so the view can be
    reconstructed and re-registered after a bot restart.
    """

    def __init__(self, ban_id: int, bot: Bot):
        super().__init__(timeout=None)
        self.ban_id = ban_id
        self.bot = bot

        approve_btn = Button(
            label="Approve duration",
            style=discord.ButtonStyle.success,
            custom_id=f"ban_approve:{ban_id}",
        )
        approve_btn.callback = self._approve
        self.add_item(approve_btn)

        deny_btn = Button(
            label="Deny and unban",
            style=discord.ButtonStyle.danger,
            custom_id=f"ban_deny:{ban_id}",
        )
        deny_btn.callback = self._deny
        self.add_item(deny_btn)

        dispute_btn = Button(
            label="Dispute",
            style=discord.ButtonStyle.primary,
            custom_id=f"ban_dispute:{ban_id}",
        )
        dispute_btn.callback = self._dispute
        self.add_item(dispute_btn)

    async def _resolve_member_name(self, guild: discord.Guild, user_id: int) -> str:
        """Resolve a display name for the banned user, falling back to the raw ID."""
        member = await self.bot.get_member_or_user(guild, user_id)
        return member.display_name if member else str(user_id)

    def _disable_all(self) -> None:
        """Disable every button in the view."""
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True

    def _disable_one(self, custom_id: str) -> None:
        """Disable only the button matching *custom_id*."""
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = item.custom_id == custom_id

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    async def _approve(self, interaction: Interaction) -> None:
        """Approve the ban duration."""
        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            ban = await session.get(Ban, self.ban_id)
            if not ban:
                await interaction.followup.send("Ban record not found.", ephemeral=True)
                return
            ban.approved = True
            user_id = ban.user_id
            await session.commit()

        member_name = await self._resolve_member_name(interaction.guild, user_id)

        await interaction.followup.send(
            f"Ban duration for {member_name} has been approved.", ephemeral=True
        )

        channel = interaction.guild.get_channel(settings.channels.SR_MOD)
        if channel:
            await channel.send(
                f"Ban duration for {member_name} has been approved by {interaction.user.display_name}."
            )

        self._disable_one(f"ban_approve:{self.ban_id}")
        await interaction.message.edit(
            content=f"{interaction.user.display_name} has made a decision: **Approved Duration** for {member_name}.",
            view=self,
        )

    async def _deny(self, interaction: Interaction) -> None:
        """Deny the ban and unban the member."""
        from src.helpers.ban import unban_member

        await interaction.response.defer(ephemeral=True)

        async with AsyncSessionLocal() as session:
            ban = await session.get(Ban, self.ban_id)
            if not ban:
                await interaction.followup.send("Ban record not found.", ephemeral=True)
                return
            user_id = ban.user_id

        member = await self.bot.get_member_or_user(interaction.guild, user_id)

        if member is None:
            # If member can't be found, we'll alert the actioner and early return
            await interaction.followup.send(
                f"User {str(user_id)} could not be found in the server.",
            )
            return

        member_name = member.display_name

        await unban_member(interaction.guild, member)

        await interaction.followup.send(
            f"Ban for {member_name} has been denied and the member will be unbanned.",
            ephemeral=True,
        )

        channel = interaction.guild.get_channel(settings.channels.SR_MOD)
        if channel:
            await channel.send(
                f"Ban for {member_name} has been denied by {interaction.user.display_name} "
                f"and the member has been unbanned."
            )

        self._disable_all()
        await interaction.message.edit(
            content=f"{interaction.user.display_name} has made a decision: **Denied and Unbanned** for {member_name}.",
            view=self,
        )

    async def _dispute(self, interaction: Interaction) -> None:
        """Open the dispute modal."""
        modal = DisputeModal(self.ban_id, self.bot, self)
        await interaction.response.send_modal(modal)


class DisputeModal(Modal):
    """Modal for disputing a ban duration."""

    def __init__(self, ban_id: int, bot: Bot, parent_view: BanDecisionView):
        super().__init__(title="Dispute Ban Duration")
        self.ban_id = ban_id
        self.bot = bot
        self.parent_view = parent_view

        self.add_item(
            InputText(
                label="New Duration",
                placeholder="Enter new duration (e.g., 10s, 5m, 2h, 1d)",
                required=True,
            )
        )

    async def callback(self, interaction: Interaction) -> None:
        """Handle the dispute duration submission."""
        from src.helpers.ban import unban_member

        new_duration_str = self.children[0].value
        dur, dur_exc = validate_duration(new_duration_str)
        if dur_exc:
            await interaction.response.send_message(dur_exc, ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            ban = await session.get(Ban, self.ban_id)
            if not ban or not ban.timestamp:
                await interaction.response.send_message(
                    f"Cannot dispute ban {self.ban_id}: record not found.",
                    ephemeral=True,
                )
                return

            ban.unban_time = dur
            ban.approved = True
            user_id = ban.user_id
            await session.commit()

        new_unban_at = datetime.fromtimestamp(dur)
        member = await self.bot.get_member_or_user(interaction.guild, user_id)
        member_name = member.display_name if member else str(user_id)

        if member:
            self.bot.loop.create_task(
                schedule(unban_member(interaction.guild, member), run_at=new_unban_at)
            )

        await interaction.response.send_message(
            f"Ban duration updated to {new_duration_str}. "
            f"The member will be unbanned on {new_unban_at.strftime('%B %d, %Y')} UTC.",
            ephemeral=True,
        )

        channel = interaction.guild.get_channel(settings.channels.SR_MOD)
        if channel:
            await channel.send(
                f"Ban duration for {member_name} updated to {new_duration_str}. "
                f"Unban scheduled for {new_unban_at.strftime('%B %d, %Y')} UTC."
            )

        self.parent_view._disable_all()
        if interaction.message:
            await interaction.message.edit(
                content=f"{interaction.user.display_name} has made a decision: **Disputed Duration** for {member_name}.",
                view=self.parent_view,
            )


async def register_ban_views(bot: Bot) -> None:
    """Re-register persistent BanDecisionView instances for all unapproved active bans.

    Call this once during bot startup (e.g. in on_ready) so that buttons on
    existing ban-decision messages continue to work after a restart.
    """
    async with AsyncSessionLocal() as session:
        stmt = select(Ban).filter(Ban.approved.is_(False), Ban.unbanned.is_(False))
        result = await session.scalars(stmt)
        bans = result.all()

    for ban in bans:
        bot.add_view(BanDecisionView(ban.id, bot))

    if bans:
        logger.info("Registered %d persistent ban decision view(s).", len(bans))
