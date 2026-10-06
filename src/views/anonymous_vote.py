"""Persistent UI and helpers for anonymous multi-user votes."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import hmac
import logging
import time
from collections import defaultdict
from datetime import datetime

import discord
from discord import Interaction, SelectOption
from discord.ui import Button, Select, View
from discord.utils import escape_markdown
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
# Under the interaction token's 15-minute life, not equal to it: py-cord starts the
# timeout clock in ViewStore.add_view, which runs only once the followup send returns,
# so an exactly-900s ballot would expire after the token and fail its own cleanup edit.
BALLOT_TIMEOUT_SECONDS = 840
# MariaDB reports 2 from ON DUPLICATE KEY UPDATE only when the stored value actually
# changed, and documents 0 for a no-op update. We never see that 0: SQLAlchemy's MySQL
# dialect ORs CLIENT_FOUND_ROWS into client_flag to get supports_sane_rowcount, so the
# server counts rows matched and 1 means "inserted or re-voted the same way".
UPSERT_ROWCOUNT_UPDATED = 2

# One pending close per session. on_ready runs on every gateway reconnect, and without this
# each reconnect would add another sleeping close task for every open vote.
_close_tasks: dict[int, asyncio.Task] = {}
# Sessions whose results are being posted right now, so a reconnect sweep cannot post them twice.
_publishing: set[int] = set()


def voter_hash(session_id: int, voter_id: int) -> str:
    """Return the keyed hash stored in place of a voter's Discord id."""
    message = f"{session_id}:{voter_id}".encode()
    return hmac.new(settings.VOTE_HMAC_SECRET.encode(), message, hashlib.sha256).hexdigest()


def _member_can_vote(member: discord.Member) -> bool:
    voter_roles = set(settings.role_groups.get("VOTE_CASTERS", []))
    return bool(voter_roles.intersection({role.id for role in member.roles}))


def _nominee_name(candidate: AnonymousVoteCandidate) -> str:
    """Nominee display name, safe to put inside embed markdown."""
    return escape_markdown(candidate.display_name)


def build_poll_embed(session: AnonymousVoteSession, candidates: list[AnonymousVoteCandidate]) -> discord.Embed:
    """Build the public poll embed. It shows no votes at all until the poll closes."""
    title = session.topic or "Anonymous vote"
    lines = [f"• **{_nominee_name(c)}** (`{c.user_id}`)" for c in candidates]
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
            "Nobody in Discord can see who voted or how. Your Discord id is not stored with your "
            "vote, only a keyed hash of it. Tallies appear when the poll closes."
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
            f"• **{_nominee_name(candidate)}** — ✓ {tally[CHOICE_APPROVE]} / ✗ {tally[CHOICE_REJECT]}"
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
    return f"Vote {action}: **{label}** for **{display_name}**. Nobody else can see your choice."


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
        values = (interaction.data or {}).get("values", [])
        if not values:
            await interaction.response.send_message("No nominee selected.", ephemeral=True)
            return
        try:
            candidate_id = int(values[0])
        except (TypeError, ValueError):
            await interaction.response.send_message("Unknown nominee.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        display_name, error = await self._resolve_nominee(candidate_id, interaction.user.id)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        await interaction.followup.send(
            f"Vote on **{display_name}**:",
            view=BallotView(self.session_id, candidate_id),
            ephemeral=True,
        )

    async def _resolve_nominee(self, candidate_id: int, voter_id: int) -> tuple[str | None, str | None]:
        """Return the nominee's escaped display name, or the error message to show the voter."""
        async with AsyncSessionLocal() as session:
            vote_session = await session.get(AnonymousVoteSession, self.session_id)
            if not vote_session or vote_session.closed:
                return None, "This poll is closed."

            candidate = await session.get(AnonymousVoteCandidate, candidate_id)
            if not candidate or candidate.session_id != self.session_id:
                return None, "Unknown nominee."
            if candidate.user_id == voter_id:
                return None, "You can't vote on yourself."

            return _nominee_name(candidate), None


class BallotView(View):
    """Private, per-voter ballot for a single nominee."""

    def __init__(self, session_id: int, candidate_id: int):
        super().__init__(timeout=BALLOT_TIMEOUT_SECONDS)
        self.session_id = session_id
        self.candidate_id = candidate_id

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
        """Persist the voter's choice and confirm it privately."""
        if not isinstance(interaction.user, discord.Member) or not _member_can_vote(interaction.user):
            await interaction.response.send_message("You are not authorized to vote in this poll.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        message = await self._record_ballot(interaction.user.id, choice)
        await interaction.followup.send(message, ephemeral=True)

    async def _record_ballot(self, voter_id: int, choice: str) -> str:
        """Upsert this voter's ballot; return the confirmation or the error to show."""
        async with AsyncSessionLocal() as session:
            vote_session = await session.get(AnonymousVoteSession, self.session_id)
            if not vote_session or vote_session.closed:
                return "This poll is closed."

            candidate = await session.get(AnonymousVoteCandidate, self.candidate_id)
            if not candidate or candidate.session_id != self.session_id:
                return "Unknown nominee."
            # Checked again here, not only when the ballot was handed out, because this is the write.
            if candidate.user_id == voter_id:
                return "You can't vote on yourself."

            display_name = _nominee_name(candidate)
            # One statement, so two clicks in flight cannot both insert and trip
            # uq_anonymous_vote_ballot_session_candidate_voter.
            result = await session.execute(
                insert(AnonymousVoteBallot)
                .values(
                    session_id=self.session_id,
                    candidate_id=self.candidate_id,
                    voter_hash=voter_hash(self.session_id, voter_id),
                    choice=choice,
                )
                .on_duplicate_key_update(choice=choice)
            )
            await session.commit()

        return _ballot_confirmation(choice, display_name, result.rowcount == UPSERT_ROWCOUNT_UPDATED)


async def _claim_close(session_id: int) -> bool:
    """Mark the session closed; False when another close already did, or the row is gone."""
    async with AsyncSessionLocal() as session:
        # Conditional UPDATE rather than read-then-write, so two closes racing each other
        # cannot both go on to publish.
        result = await session.execute(
            update(AnonymousVoteSession)
            .where(AnonymousVoteSession.id == session_id, AnonymousVoteSession.closed.is_(False))
            .values(closed=True)
        )
        if result.rowcount == 0:
            logger.debug("Anonymous vote session %s is already closed or gone.", session_id)
            return False
        await session.commit()
        return True


async def _load_results(
    session_id: int,
) -> tuple[discord.Embed, list[AnonymousVoteCandidate], int, int | None] | None:
    """Return what publishing needs, or None when the session is gone or already published."""
    async with AsyncSessionLocal() as session:
        vote_session = await session.scalar(
            select(AnonymousVoteSession)
            .where(AnonymousVoteSession.id == session_id)
            .options(
                selectinload(AnonymousVoteSession.candidates),
                selectinload(AnonymousVoteSession.ballots),
            )
        )
        if vote_session is None:
            logger.warning("Anonymous vote session %s vanished before its results were posted.", session_id)
            return None
        if vote_session.published_at is not None:
            return None

        candidates = list(vote_session.candidates)
        results_embed = build_results_embed(vote_session, candidates, list(vote_session.ballots))
        return results_embed, candidates, vote_session.channel_id, vote_session.message_id


async def _mark_published(session_id: int) -> None:
    """Record that the results are out, so startup does not post them again."""
    async with AsyncSessionLocal() as session:
        await session.execute(
            update(AnonymousVoteSession)
            .where(AnonymousVoteSession.id == session_id, AnonymousVoteSession.published_at.is_(None))
            .values(published_at=int(time.time()))
        )
        await session.commit()


async def _resolve_poll_channel(bot: Bot, channel_id: int, session_id: int) -> discord.abc.Messageable | None:
    """Return the channel the poll was posted in, fetching it when it is not cached."""
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel
    try:
        return await bot.fetch_channel(channel_id)
    except discord.HTTPException:
        logger.exception(
            "Failed to fetch channel %s for vote session %s. Results will be retried on the next "
            "startup or reconnect.",
            channel_id,
            session_id,
        )
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


async def _send_results(channel: discord.abc.Messageable, results_embed: discord.Embed, session_id: int) -> bool:
    """Post results as a new message; False when that failed too."""
    try:
        await channel.send(embed=results_embed)
        return True
    except discord.HTTPException:
        logger.exception(
            "Failed to post results for vote session %s. The ballots are still stored, and posting "
            "is retried on the next startup or reconnect.",
            session_id,
        )
        return False


async def publish_vote_results(bot: Bot, session_id: int) -> None:
    """Post the results of a closed session, unless they are already out."""
    if session_id in _publishing:
        return
    _publishing.add(session_id)
    try:
        loaded = await _load_results(session_id)
        if loaded is None:
            return
        results_embed, candidates, channel_id, message_id = loaded

        channel = await _resolve_poll_channel(bot, channel_id, session_id)
        if channel is None:
            return

        view = AnonymousVoteView(session_id, bot, candidates)
        for item in view.children:
            item.disabled = True

        posted = await _edit_poll_with_results(channel, message_id, results_embed, view, session_id)
        if not posted:
            posted = await _send_results(channel, results_embed, session_id)
        # A restart between the post and this write posts the results a second time. That is
        # the safer way to fail: a duplicate is visible, missing results are not.
        if posted:
            await _mark_published(session_id)
    finally:
        _publishing.discard(session_id)


async def close_anonymous_vote(bot: Bot, session_id: int) -> None:
    """Close a vote session, post totals, and disable controls."""
    if await _claim_close(session_id):
        await publish_vote_results(bot, session_id)


def schedule_vote_close(bot: Bot, session_id: int, closes_at_ts: int) -> None:
    """Schedule auto-close for a vote session, unless one is already pending."""
    pending = _close_tasks.get(session_id)
    if pending is not None and not pending.done():
        return

    task = bot.loop.create_task(
        schedule(close_anonymous_vote(bot, session_id), datetime.fromtimestamp(closes_at_ts))
    )
    _close_tasks[session_id] = task

    def _forget(done: asyncio.Task) -> None:
        if _close_tasks.get(session_id) is done:
            del _close_tasks[session_id]

    task.add_done_callback(_forget)


async def register_anonymous_vote_views(bot: Bot) -> None:
    """Re-register open vote views, reschedule their closes, and retry unpublished results."""
    async with AsyncSessionLocal() as session:
        open_sessions = list(
            (
                await session.scalars(
                    select(AnonymousVoteSession)
                    .where(AnonymousVoteSession.closed.is_(False))
                    .options(selectinload(AnonymousVoteSession.candidates))
                )
            ).all()
        )
        unpublished_ids = list(
            (
                await session.scalars(
                    select(AnonymousVoteSession.id).where(
                        AnonymousVoteSession.closed.is_(True),
                        AnonymousVoteSession.published_at.is_(None),
                    )
                )
            ).all()
        )

    now = int(time.time())
    for vote_session in open_sessions:
        bot.add_view(AnonymousVoteView(vote_session.id, bot, vote_session.candidates))
        if vote_session.closes_at <= now:
            bot.loop.create_task(close_anonymous_vote(bot, vote_session.id))
        else:
            schedule_vote_close(bot, vote_session.id, vote_session.closes_at)

    for session_id in unpublished_ids:
        bot.loop.create_task(publish_vote_results(bot, session_id))

    if open_sessions:
        logger.info("Registered %d open anonymous vote session(s).", len(open_sessions))
    if unpublished_ids:
        logger.warning("Retrying results for %d closed but unpublished vote session(s).", len(unpublished_ids))
