from datetime import datetime

import discord
from discord import Guild, Interaction, Member, User
from discord.ui import Button, InputText, Modal, View
from sqlalchemy import select

from src.bot import Bot
from src.core import settings
from src.database.models import Ban
from src.database.session import AsyncSessionLocal
from src.helpers.duration import validate_duration
from src.helpers.schedule import schedule


class BanDecisionView(View):
    """View for making decisions on a ban duration."""

    def __init__(self, ban_id: int, bot: Bot, guild: Guild, member: Member | User, end_date: str, reason: str):
        super().__init__(timeout=None)
        self.ban_id = ban_id
        self.bot = bot
        self.guild = guild
        self.member = member
        self.end_date = end_date
        self.reason = reason

    async def update_message(self, interaction: Interaction, decision: str) -> None:
        """Update the message to reflect the decision."""
        admin_name = interaction.user.display_name
        decision_message = f"{admin_name} has made a decision: **{decision}** for {self.member.display_name}."
        await interaction.message.edit(content=decision_message, view=self)

    async def disable_all_buttons(self) -> None:
        """Disable all buttons in the view."""
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True

    async def update_buttons(self, clicked_button_id: str) -> None:
        """Disable the clicked button and enable all others."""
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = item.custom_id == clicked_button_id

    @discord.ui.button(label="Approve duration", style=discord.ButtonStyle.success, custom_id="approve_button")
    async def approve_button(self, button: Button, interaction: Interaction) -> None:
        """Approve the ban duration."""
        await interaction.response.send_message(
            f"Ban duration for {self.member.display_name} has been approved.", ephemeral=True
        )
        async with AsyncSessionLocal() as session:
            stmt = select(Ban).filter(Ban.id == self.ban_id)
            result = await session.scalars(stmt)
            ban = result.first()
            if ban:
                ban.approved = True
                await session.commit()
        await self.guild.get_channel(settings.channels.SR_MOD).send(
            f"Ban duration for {self.member.display_name} has been approved by {interaction.user.display_name}."
        )
        # Disable the clicked button and enable others
        await self.update_buttons("approve_button")
        await interaction.message.edit(view=self)
        await self.update_message(interaction, "Approved Duration")

    @discord.ui.button(label="Deny and unban", style=discord.ButtonStyle.danger, custom_id="deny_button")
    async def deny_button(self, button: Button, interaction: Interaction) -> None:
        """Deny the ban duration and unban the member."""
        from src.helpers.ban import unban_member
        await interaction.response.send_message(
            f"Ban for {self.member.display_name} has been denied and the member will be unbanned.", ephemeral=True
        )
        await unban_member(self.guild, self.member)
        await self.guild.get_channel(settings.channels.SR_MOD).send(
            f"Ban for {self.member.display_name} has been denied by {interaction.user.display_name} and the member has been unbanned."
        )
        # Disable all buttons after denial
        await self.disable_all_buttons()
        await interaction.message.edit(view=self)
        await self.update_message(interaction, "Denied and Unbanned")

    @discord.ui.button(label="Dispute", style=discord.ButtonStyle.primary, custom_id="dispute_button")
    async def dispute_button(self, button: Button, interaction: Interaction) -> None:
        """Dispute the ban duration."""
        modal = DisputeModal(self.ban_id, self.bot, self.guild, self.member, self.end_date, self.reason, self)
        await interaction.response.send_modal(modal)


class DisputeModal(Modal):
    """Modal for disputing a ban duration."""

    def __init__(self, ban_id: int, bot: Bot, guild: Guild, member: Member | User, end_date: str, reason: str, parent_view: BanDecisionView):
        super().__init__(title="Dispute Ban Duration")
        self.ban_id = ban_id
        self.bot = bot
        self.guild = guild
        self.member = member
        self.end_date = end_date
        self.reason = reason
        self.parent_view = parent_view  # Store the parent view

        # Add InputText for duration
        self.add_item(
            InputText(label="New Duration", placeholder="Enter new duration (e.g., 10s, 5m, 2h, 1d)", required=True)
        )

    async def callback(self, interaction: Interaction) -> None:
        """Handle the dispute duration callback."""
        from src.helpers.ban import unban_member
        new_duration_str = self.children[0].value

        # Validate duration using `validate_duration`
        dur, dur_exc = validate_duration(new_duration_str)
        if dur_exc:
            # Send an ephemeral message if the duration is invalid
            await interaction.response.send_message(dur_exc, ephemeral=True)
            return

        # Proceed with updating the ban record if the duration is valid
        async with AsyncSessionLocal() as session:
            ban = await session.get(Ban, self.ban_id)

            if not ban or not ban.timestamp:
                await interaction.response.send_message(f"Cannot dispute ban {self.ban_id}: record not found.", ephemeral=True)
                return

            # Update the ban's unban time and approve the dispute
            ban.unban_time = dur
            ban.approved = True
            await session.commit()

        # Schedule the unban based on the new duration
        new_unban_at = datetime.fromtimestamp(dur)
        member = await self.bot.get_member_or_user(self.guild, ban.user_id)
        if member:
            self.bot.loop.create_task(schedule(unban_member(self.guild, member), run_at=new_unban_at))

        # Notify the user and moderators of the updated ban duration
        await interaction.response.send_message(
            f"Ban duration updated to {new_duration_str}. The member will be unbanned on {new_unban_at.strftime('%B %d, %Y')} UTC.",
            ephemeral=True
        )
        await self.guild.get_channel(settings.channels.SR_MOD).send(
            f"Ban duration for {self.member.display_name} updated to {new_duration_str}. Unban scheduled for {new_unban_at.strftime('%B %d, %Y')} UTC."
        )

        # Disable buttons and update message on the parent view after dispute
        await self.parent_view.update_message(interaction, "Disputed Duration")
