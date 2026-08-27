"""Persistent UI and helpers for anonymous multi-user votes."""

from __future__ import annotations

import contextlib
import logging
import time
from collections import defaultdict
from datetime import datetime

import discord
from discord import Interaction, SelectOption
from discord.ui import Button, Select, View
from sqlalchemy import select, update
from sqlalchemy.dialects.mysql import insert
from sqlalchemy.orm import selectinload

from src.bot import Bot
from src.core import settings
from src.database.models import AnonymousVoteBallot, AnonymousVoteCandidate, AnonymousVoteSession
from src.database.session import AsyncSessionLocal
from src.helpers.schedule import schedule

logger = logging.getLogger(__name__)

CHOICE_APPROVE = "approve"
CHOICE_REJECT = "reject"
# Neutral marker shown per ballot cast (does not reveal approve vs reject).
VOTE_ACTIVITY_BOX = "⬜"
# Keep embed descriptions safely under Discord's 4096-char limit.
MAX_ACTIVITY_BOXES_PER_NOMINEE = 40
# Under the interaction token's 15-minute life, not equal to it: py-cord starts the
# timeout clock in ViewStore.add_view, which runs only once the followup send returns,
# so an exactly-900s ballot would expire after the token and fail its own cleanup edit.
BALLOT_TIMEOUT_SECONDS = 840
# MariaDB reports 2 from ON DUPLICATE KEY UPDATE only when the stored value actually
# changed, and documents 0 for a no-op update. We never see that 0: SQLAlchemy's MySQL
# dialect ORs CLIENT_FOUND_ROWS into client_flag to get supports_sane_rowcount, so the
# server counts rows matched and 1 means "inserted or re-voted the same way".
UPSERT_ROWCOUNT_UPDATED = 2


def _member_can_vote(member: discord.Member) -> bool:
    voter_roles = set(settings.role_groups.get("VOTE_CASTERS", []))
    return bool(voter_roles.intersection({role.id for role in member.roles}))


def _ballot_counts_by_candidate(ballots: list[AnonymousVoteBallot]) -> dict[int, int]:
    counts: dict[int, int] = defaultdict(int)
    for ballot in ballots:
        counts[ballot.candidate_id] += 1
    return counts


def _format_nominee_line(candidate: AnonymousVoteCandidate, vote_count: int) -> str:
    """Format a nominee line with one activity box per cast ballot."""
    line = f"• **{candidate.display_name}** (`{candidate.user_id}`)"
    if vote_count <= 0:
        return line
    shown = min(vote_count, MAX_ACTIVITY_BOXES_PER_NOMINEE)
    boxes = VOTE_ACTIVITY_BOX * shown
    if vote_count > MAX_ACTIVITY_BOXES_PER_NOMINEE:
        boxes += "…"
    return f"{line} {boxes}"


def build_poll_embed(
    session: AnonymousVoteSession,
    candidates: list[AnonymousVoteCandidate],
    ballots: list[AnonymousVoteBallot] | None = None,
) -> discord.Embed:
    """Build the public poll embed (no approve/reject tallies)."""
    title = session.topic or "Anonymous vote"
    counts = _ballot_counts_by_candidate(ballots or [])
    lines = [_format_nominee_line(c, counts.get(c.id, 0)) for c in candidates]
    embed = discord.Embed(
        title=title,
        description="\n".join(lines) if lines else "No nominees.",
        color=0x9ACC14,
    )
    embed.add_field(
        name="How to vote",
        value=(
            "1. Select a nominee from the menu\n"
            "2. Press **Approve** or **Reject** on the private ballot you receive\n"
            f"Each {VOTE_ACTIVITY_BOX} next to a name means someone voted on them "
            "(not whether it was approve or reject). "
            "Votes stay anonymous; exact tallies appear when the poll closes."
        ),
        inline=False,
    )
    embed.add_field(
        name="Closes",
        value=f"<t:{session.closes_at}:F> (<t:{session.closes_at}:R>)",
        inline=False,
    )
    embed.set_footer(text=f"Session #{session.id}")
    return embed


def build_results_embed(
    session: AnonymousVoteSession,
    candidates: list[AnonymousVoteCandidate],
    ballots: list[AnonymousVoteBallot],
) -> discord.Embed:
    """Build results embed with totals only (no voter identities)."""
    counts: dict[int, dict[str, int]] = defaultdict(lambda: {CHOICE_APPROVE: 0, CHOICE_REJECT: 0})
    for ballot in ballots:
        if ballot.choice in (CHOICE_APPROVE, CHOICE_REJECT):
            counts[ballot.candidate_id][ballot.choice] += 1

    title = session.topic or "Anonymous vote"
    lines = []
    for candidate in candidates:
        tally = counts[candidate.id]
        lines.append(
            f"• **{candidate.display_name}** — ✓ {tally[CHOICE_APPROVE]} / ✗ {tally[CHOICE_REJECT]}"
        )

    embed = discord.Embed(
        title=f"Results: {title}",
        description="\n".join(lines) if lines else "No nominees.",
        color=0x5865F2,
    )
    embed.set_footer(text=f"Session #{session.id} • Closed • Voter identities are not shown")
    return embed


def _ballot_confirmation(choice: str, display_name: str, updated: bool) -> str:
    """Word the private vote confirmation."""
    label = "Approve" if choice == CHOICE_APPROVE else "Reject"
    action = "updated" if updated else "recorded"
    return (
        f"Vote {action}: **{label}** for **{display_name}**. "
        "Your choice is anonymous; only a neutral activity box is shown publicly."
    )


def _candidate_options(candidates: list[AnonymousVoteCandidate] | None) -> list[SelectOption]:
    """Build the nominee select options, with a disabled placeholder when there are none."""
    options = [
        SelectOption(
            label=(c.display_name[:100] or str(c.user_id)),
            value=str(c.id),
            description=f"ID {c.user_id}"[:100],
        )
        for c in (candidates or [])
    ]
    return options[:25] or [SelectOption(label="No nominees", value="0", default=True)]


class AnonymousVoteView(View):
    """Persistent view: pick a nominee, then vote on a private ballot."""

    def __init__(
        self,
        session_id: int,
        bot: Bot,
        candidates: list[AnonymousVoteCandidate] | None = None,
    ):
        super().__init__(timeout=None)
        self.session_id = session_id
        self.bot = bot

        nominee_select = Select(
            placeholder="Select a nominee to vote on",
            options=_candidate_options(candidates),
            custom_id=f"anon_vote_select:{session_id}",
            min_values=1,
            max_values=1,
            disabled=not candidates,
        )
        nominee_select.callback = self._on_select
        self.add_item(nominee_select)

    async def _on_select(self, interaction: Interaction) -> None:
        """Send the voter a private ballot for the nominee they picked."""
        if not isinstance(interaction.user, discord.Member) or not _member_can_vote(interaction.user):
            await interaction.response.send_message("You are not authorized to vote in this poll.", ephemeral=True)
            return

        # Read the pick off this interaction's own payload, never off the Select item:
        # the item is shared by every voter and ViewStore.dispatch overwrites its state
        # synchronously while callbacks run in later tasks, so voters would cross nominees.
        values = interaction.data.get("values", [])
        if not values:
            await interaction.response.send_message("No nominee selected.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        candidate_id = int(values[0])
        display_name, error = await self._resolve_nominee(candidate_id)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        await interaction.followup.send(
            f"Vote on **{display_name}**:",
            view=BallotView(self.session_id, candidate_id, interaction.message),
            ephemeral=True,
        )

    async def _resolve_nominee(self, candidate_id: int) -> tuple[str | None, str | None]:
        """Return the nominee's display name, or the error message to show the voter."""
        async with AsyncSessionLocal() as session:
            vote_session = await session.get(AnonymousVoteSession, self.session_id)
            if not vote_session or vote_session.closed:
                return None, "This poll is closed."

            candidate = await session.get(AnonymousVoteCandidate, candidate_id)
            if not candidate or candidate.session_id != self.session_id:
                return None, "Unknown nominee."

            return candidate.display_name, None


class BallotView(View):
    """Private, per-voter ballot for a single nominee."""

    def __init__(self, session_id: int, candidate_id: int, poll_message: discord.Message | None):
        super().__init__(timeout=BALLOT_TIMEOUT_SECONDS)
        self.session_id = session_id
        self.candidate_id = candidate_id
        self.poll_message = poll_message

        approve_btn = Button(label="Approve", style=discord.ButtonStyle.success, emoji="✅")
        approve_btn.callback = self._on_approve
        self.add_item(approve_btn)

        reject_btn = Button(label="Reject", style=discord.ButtonStyle.danger, emoji="❌")
        reject_btn.callback = self._on_reject
        self.add_item(reject_btn)

    async def _on_approve(self, interaction: Interaction) -> None:
        """Record an approving ballot."""
        await self._cast_vote(interaction, CHOICE_APPROVE)

    async def _on_reject(self, interaction: Interaction) -> None:
        """Record a rejecting ballot."""
        await self._cast_vote(interaction, CHOICE_REJECT)

    async def on_timeout(self) -> None:
        """
        Disable the ballot on expiry.

        py-cord evicts a finished view from the ViewStore, so a later click would get
        no response at all rather than an error the voter can act on.
        """
        self.disable_all_items()
        if self.message is None:
            return
        with contextlib.suppress(discord.HTTPException):
            await self.message.edit(
                content="This ballot expired. Pick the nominee again to vote.", view=self
            )

    async def _cast_vote(self, interaction: Interaction, choice: str) -> None:
        """Persist the voter's choice, then refresh the public poll embed."""
        if not isinstance(interaction.user, discord.Member) or not _member_can_vote(interaction.user):
            await interaction.response.send_message("You are not authorized to vote in this poll.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        confirmation, poll_embed, error = await self._record_ballot(interaction.user.id, choice)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        await interaction.followup.send(confirmation, ephemeral=True)
        await self._refresh_poll_message(poll_embed)

    async def _record_ballot(
        self, voter_id: int, choice: str
    ) -> tuple[str | None, discord.Embed | None, str | None]:
        """Upsert this voter's ballot and rebuild the poll embed, or return an error message."""
        async with AsyncSessionLocal() as session:
            vote_session = await session.get(AnonymousVoteSession, self.session_id)
            if not vote_session or vote_session.closed:
                return None, None, "This poll is closed."

            candidate = await session.get(AnonymousVoteCandidate, self.candidate_id)
            if not candidate or candidate.session_id != self.session_id:
                return None, None, "Unknown nominee."

            display_name = candidate.display_name
            # One statement, so two clicks in flight cannot both insert and trip
            # uq_anonymous_vote_ballot_session_candidate_voter.
            result = await session.execute(
                insert(AnonymousVoteBallot)
                .values(
                    session_id=self.session_id,
                    candidate_id=self.candidate_id,
                    voter_id=voter_id,
                    choice=choice,
                )
                .on_duplicate_key_update(choice=choice)
            )
            await session.commit()

            loaded = await session.scalar(
                select(AnonymousVoteSession)
                .where(AnonymousVoteSession.id == self.session_id)
                .options(
                    selectinload(AnonymousVoteSession.candidates),
                    selectinload(AnonymousVoteSession.ballots),
                )
            )
            poll_embed = (
                build_poll_embed(loaded, list(loaded.candidates), list(loaded.ballots)) if loaded else None
            )

        confirmation = _ballot_confirmation(
            choice, display_name, result.rowcount == UPSERT_ROWCOUNT_UPDATED
        )
        return confirmation, poll_embed, None

    async def _refresh_poll_message(self, poll_embed: discord.Embed | None) -> None:
        """Redraw the public poll message so the new activity box shows."""
        if poll_embed is None or self.poll_message is None:
            return
        try:
            await self.poll_message.edit(embed=poll_embed)
        except discord.HTTPException:
            logger.exception("Failed to refresh poll embed for session %s after vote.", self.session_id)


async def _close_vote_session(
    session_id: int,
) -> tuple[discord.Embed, list[AnonymousVoteCandidate], int, int | None] | None:
    """Claim the close atomically and return what publishing its results needs."""
    async with AsyncSessionLocal() as session:
        # Conditional UPDATE rather than read-then-write: on_ready re-schedules a close
        # on every reconnect, so a long vote accumulates closes that all fire at once
        # and would otherwise each publish a results message.
        result = await session.execute(
            update(AnonymousVoteSession)
            .where(AnonymousVoteSession.id == session_id, AnonymousVoteSession.closed.is_(False))
            .values(closed=True)
        )
        if result.rowcount == 0:
            logger.debug("Anonymous vote session %s is already closed or gone.", session_id)
            return None
        await session.commit()

        vote_session = await session.scalar(
            select(AnonymousVoteSession)
            .where(AnonymousVoteSession.id == session_id)
            .options(
                selectinload(AnonymousVoteSession.candidates),
                selectinload(AnonymousVoteSession.ballots),
            )
        )
        if vote_session is None:
            logger.warning("Anonymous vote session %s vanished after its close was claimed.", session_id)
            return None

        candidates = list(vote_session.candidates)
        results_embed = build_results_embed(vote_session, candidates, list(vote_session.ballots))
        return results_embed, candidates, vote_session.channel_id, vote_session.message_id


async def _resolve_poll_channel(bot: Bot, channel_id: int, session_id: int) -> discord.abc.Messageable | None:
    """Return the channel the poll was posted in, fetching it when it is not cached."""
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel
    try:
        return await bot.fetch_channel(channel_id)
    except discord.HTTPException:
        logger.exception("Failed to fetch channel %s for vote session %s", channel_id, session_id)
        return None


async def _edit_poll_with_results(
    channel: discord.abc.Messageable,
    message_id: int | None,
    results_embed: discord.Embed,
    view: AnonymousVoteView,
    session_id: int,
) -> bool:
    """Replace the poll message with its results; False when it could not be updated."""
    if not message_id:
        return False
    try:
        message = await channel.fetch_message(message_id)
        await message.edit(
            content="This anonymous vote is closed. Results below.",
            embed=results_embed,
            view=view,
        )
        return True
    except discord.HTTPException:
        logger.exception(
            "Failed to edit poll message %s for session %s; posting results separately.",
            message_id,
            session_id,
        )
        return False


async def _send_results(
    channel: discord.abc.Messageable, results_embed: discord.Embed, session_id: int
) -> None:
    """Post results as a new message. Swallowing here loses the tallies, so log loudly."""
    try:
        await channel.send(embed=results_embed)
    except discord.HTTPException:
        logger.exception(
            "Failed to post results for vote session %s; the tallies are now unrecoverable.",
            session_id,
        )


async def close_anonymous_vote(bot: Bot, session_id: int) -> None:
    """Close a vote session, post totals, and disable controls."""
    closed = await _close_vote_session(session_id)
    if closed is None:
        return
    results_embed, candidates, channel_id, message_id = closed

    channel = await _resolve_poll_channel(bot, channel_id, session_id)
    if channel is None:
        return

    view = AnonymousVoteView(session_id, bot, candidates)
    for item in view.children:
        item.disabled = True

    if not await _edit_poll_with_results(channel, message_id, results_embed, view, session_id):
        await _send_results(channel, results_embed, session_id)


def schedule_vote_close(bot: Bot, session_id: int, closes_at_ts: int) -> None:
    """Schedule auto-close for a vote session on the bot event loop."""
    bot.loop.create_task(
        schedule(close_anonymous_vote(bot, session_id), datetime.fromtimestamp(closes_at_ts))
    )


async def register_anonymous_vote_views(bot: Bot) -> None:
    """Re-register open vote views and reschedule their closes after restart."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(AnonymousVoteSession)
            .where(AnonymousVoteSession.closed.is_(False))
            .options(selectinload(AnonymousVoteSession.candidates))
        )
        result = await session.scalars(stmt)
        open_sessions = list(result.all())

    now = int(time.time())
    for vote_session in open_sessions:
        bot.add_view(AnonymousVoteView(vote_session.id, bot, vote_session.candidates))
        if vote_session.closes_at <= now:
            bot.loop.create_task(close_anonymous_vote(bot, vote_session.id))
        else:
            schedule_vote_close(bot, vote_session.id, vote_session.closes_at)

    if open_sessions:
        logger.info("Registered %d open anonymous vote session(s).", len(open_sessions))
