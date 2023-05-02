import logging
from datetime import date, timedelta
from typing import Callable, List, Sequence

import arrow
import discord
from discord import ApplicationContext, Embed, Interaction, NotFound, WebhookMessage, slash_command
from discord.ext import commands
from discord.ext.commands import has_any_role
from sqlalchemy import select

from src.bot import Bot
from src.core import settings
from src.database.models import Infraction, UserNote
from src.database.session import AsyncSessionLocal
from src.helpers.getters import get_member_safe

logger = logging.getLogger(__name__)


class HistoryCog(commands.Cog):
    """Given a Discord user, show their history (notes, infractions, etc.)."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @slash_command(
        guild_ids=settings.guild_ids,
        description="Print the infraction history and basic details about the Discord user.",
    )
    @has_any_role(
        *settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_MODS"),
        *settings.role_groups.get("ALL_HTB_STAFF")
    )
    async def history(self, ctx: ApplicationContext, user: discord.Member) -> Interaction | WebhookMessage:
        """Print the infraction history and basic details about the Discord user."""
        left = False
        member = await get_member_safe(user, ctx.guild)
        # If member is None it means the user is not in the guild, so try to get the user from discord.
        if member is None:
            try:
                member = await self.bot.fetch_user(user.id)
            except NotFound:
                return await ctx.respond(
                    "Error: cannot get history - user was deleted from Discord entirely.", delete_after=15
                )

            left = True

        today_date = arrow.utcnow().date()

        async with AsyncSessionLocal() as session:
            stmt = select(UserNote).filter(UserNote.user_id == user.id)
            result = await session.scalars(stmt)
            notes: Sequence[UserNote] = result.all()

            stmt = select(Infraction).filter(Infraction.user_id == user.id)
            result = await session.scalars(stmt)
            infractions: Sequence[Infraction] = result.all()

        expired_infractions = sum(1 for inf in infractions if (inf.date - today_date).days < -90)

        if left:
            join_date = "Left"
        else:
            join_date = member.joined_at.date()

        creation_date = member.created_at.date()
        strike_value = 0
        for infraction in infractions:
            strike_value += infraction.weight

        summary_text = f"""
    **{member.name}**
    Total infraction(s): **{len(infractions)}**
    Expired: **{expired_infractions}**
    Active: **{len(infractions) - expired_infractions}**
    Current strike value: **{strike_value}/3**
    Join date: **{join_date}**
    Creation Date: **{creation_date}**
    """
        if strike_value >= 3:
            summary_text += f"\n**Review needed** by Sr. Mod or Admin: **{strike_value}/3 strikes**."

        embed = Embed(title="Moderation History", description=f"{summary_text}", color=0xB98700)
        if member.avatar is not None:
            embed.set_thumbnail(url=member.avatar)
        self._embed_titles_of(
            embed,
            entry_type="infractions", history_entries=infractions, today_date=today_date,
            entry_handler=self._produce_inf_text,
        )
        self._embed_titles_of(
            embed,
            entry_type="notes", history_entries=notes, today_date=today_date,
            entry_handler=self._produce_note_text
        )

        if len(embed) > 6000:
            return await ctx.respond(f"History embed is too big to send ({len(embed)}/6000 allowed chars).")
        else:
            return await ctx.respond(embed=embed)

    @staticmethod
    def _embed_titles_of(
        embed: Embed, entry_type: str, history_entries: Sequence[UserNote | Infraction], today_date: date,
        entry_handler: Callable[[UserNote | Infraction, date], str]
    ) -> None:
        """
        Add formatted titles of a specific entry type to the given embed.

        This function populates the provided embed with "title" fields, containing the text
        formatted by the entry_handler for the specified entry_type (e.g., infractions or notes).
        The embed is mutated in-place by this function.

        Args:
            embed (Embed): The embed object to populate with title fields.
            entry_type (str): The type of history entries being processed (e.g., "Infraction", "Note").
            history_entries (list): A list of history entries of the specified entry_type.
            today_date (date): The current date, used for relative date formatting.
            entry_handler (Callable[[UserNote, date], str]): A function that takes a history entry and the current date
                                                             as arguments, and returns a formatted string.

        Returns:
            None
        """
        entry_records: List[List[str]] = [[]]
        if history_entries is not None:
            current_row = 0
            for entry in history_entries:
                entry_text = entry_handler(entry, today_date=today_date)

                if sum(len(r) for r in entry_records[current_row]) + len(entry_text) > 1000:
                    entry_records.append(list())
                    current_row += 1
                entry_records[current_row].append(entry_text)

        if len(entry_records[0]) == 0:
            embed.add_field(name=f"{entry_type.capitalize()}:", value=f"No {entry_type.lower()}.", inline=False)
        else:
            for i in range(0, len(entry_records)):
                embed.add_field(
                    name=f"{entry_type.capitalize()} ({i + 1}/{len(entry_records)}):",
                    value="\n\n".join(entry_records[i]),
                    inline=False,
                )

    @staticmethod
    def _produce_note_text(note: UserNote, today_date: date) -> str:
        """Produces a single note line in the embed containing basic information about the note and the note itself."""
        return (
            f"#{note.id} by <@{note.moderator_id}> on {note.date}: "
            f"{note.note if len(note.note) <= 300 else note.note[:300] + '...'}"
        )

    @staticmethod
    def _produce_inf_text(infraction: Infraction, today_date: date) -> str:
        """Produces a formatted block of text of an infraction, containing all relevant information."""
        two_weeks_ago = today_date - timedelta(days=14)
        expired_status = "Active" if infraction.date >= two_weeks_ago else "Expired"

        return f"""#{infraction.id}, weight: {infraction.weight}
    Issued by <@{infraction.moderator_id}> on {infraction.date} ({expired_status}):
    {infraction.reason if len(infraction.reason) <= 300 else infraction.reason[:300] + '...'}"""


def setup(bot: Bot) -> None:
    """Load the `HistoryCog` cog."""
    bot.add_cog(HistoryCog(bot))
