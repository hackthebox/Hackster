"""Persistent UI and helpers for anonymous multi-user votes."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime

import discord
from discord import Interaction, SelectOption
from discord.ui import Button, Select, View
from sqlalchemy import select
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

_pending_selection: dict[tuple[int, int], int] = {}


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
            "2. Press **Approve** or **Reject**\n"
            f"Each {VOTE_ACTIVITY_BOX} next to a name means someone voted on them "
            "(not whether it was approve or reject). "
            "Votes stay anonymous; exact tallies appear when the poll closes."
        ),
        inline=False,
    )
    embed.add_field(
        name="Closes",
        value=discord.utils.format_dt(session.closes_at, style="F")
        + f" ({discord.utils.format_dt(session.closes_at, style='R')})",
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


class AnonymousVoteView(View):
    """Persistent view: select a nominee, then approve/reject anonymously."""

    def __init__(
        self,
        session_id: int,
        bot: Bot,
        candidates: list[AnonymousVoteCandidate] | None = None,
    ):
        super().__init__(timeout=None)
        self.session_id = session_id
        self.bot = bot

        options = [
            SelectOption(
                label=(c.display_name[:100] or str(c.user_id)),
                value=str(c.id),
                description=f"ID {c.user_id}"[:100],
            )
            for c in (candidates or [])
        ]
        if not options:
            options = [SelectOption(label="No nominees", value="0", default=True)]

        select = Select(
            placeholder="Select a nominee to vote on",
            options=options[:25],
            custom_id=f"anon_vote_select:{session_id}",
            min_values=1,
            max_values=1,
            disabled=not candidates,
        )

        async def on_select(interaction: Interaction) -> None:
            await self._handle_select(interaction, select.values)

        select.callback = on_select
        self.add_item(select)

        approve_btn = Button(
            label="Approve",
            style=discord.ButtonStyle.success,
            emoji="✅",
            custom_id=f"anon_vote_approve:{session_id}",
        )
        approve_btn.callback = self._on_approve
        self.add_item(approve_btn)

        reject_btn = Button(
            label="Reject",
            style=discord.ButtonStyle.danger,
            emoji="❌",
            custom_id=f"anon_vote_reject:{session_id}",
        )
        reject_btn.callback = self._on_reject
        self.add_item(reject_btn)

    async def _handle_select(self, interaction: Interaction, values: list[str]) -> None:
        if not isinstance(interaction.user, discord.Member) or not _member_can_vote(interaction.user):
            await interaction.response.send_message(
                "You are not authorized to vote in this poll.", ephemeral=True
            )
            return

        if not values:
            await interaction.response.send_message("No nominee selected.", ephemeral=True)
            return

        candidate_id = int(values[0])
        if candidate_id <= 0:
            await interaction.response.send_message("Invalid nominee.", ephemeral=True)
            return

        async with AsyncSessionLocal() as session:
            vote_session = await session.get(AnonymousVoteSession, self.session_id)
            if not vote_session or vote_session.closed:
                await interaction.response.send_message("This poll is closed.", ephemeral=True)
                return
            candidate = await session.get(AnonymousVoteCandidate, candidate_id)
            if not candidate or candidate.session_id != self.session_id:
                await interaction.response.send_message("Unknown nominee.", ephemeral=True)
                return
            display_name = candidate.display_name

        _pending_selection[(self.session_id, interaction.user.id)] = candidate_id
        await interaction.response.send_message(
            f"Selected **{display_name}**. Now press **Approve** or **Reject**.",
            ephemeral=True,
        )

    async def _on_approve(self, interaction: Interaction) -> None:
        await self._cast_vote(interaction, CHOICE_APPROVE)

    async def _on_reject(self, interaction: Interaction) -> None:
        await self._cast_vote(interaction, CHOICE_REJECT)

    async def _cast_vote(self, interaction: Interaction, choice: str) -> None:
        if not isinstance(interaction.user, discord.Member) or not _member_can_vote(interaction.user):
            await interaction.response.send_message(
                "You are not authorized to vote in this poll.", ephemeral=True
            )
            return

        candidate_id = _pending_selection.get((self.session_id, interaction.user.id))
        if not candidate_id:
            await interaction.response.send_message(
                "Select a nominee from the menu first, then press Approve or Reject.",
                ephemeral=True,
            )
            return

        poll_embed: discord.Embed | None = None
        async with AsyncSessionLocal() as session:
            vote_session = await session.get(AnonymousVoteSession, self.session_id)
            if not vote_session or vote_session.closed:
                await interaction.response.send_message("This poll is closed.", ephemeral=True)
                return

            candidate = await session.get(AnonymousVoteCandidate, candidate_id)
            if not candidate or candidate.session_id != self.session_id:
                await interaction.response.send_message("Unknown nominee.", ephemeral=True)
                return

            stmt = select(AnonymousVoteBallot).where(
                AnonymousVoteBallot.session_id == self.session_id,
                AnonymousVoteBallot.candidate_id == candidate_id,
                AnonymousVoteBallot.voter_id == interaction.user.id,
            )
            ballot = await session.scalar(stmt)
            if ballot:
                ballot.choice = choice
                action = "updated"
            else:
                session.add(
                    AnonymousVoteBallot(
                        session_id=self.session_id,
                        candidate_id=candidate_id,
                        voter_id=interaction.user.id,
                        choice=choice,
                    )
                )
                action = "recorded"

            display_name = candidate.display_name
            await session.commit()

            loaded = await session.scalar(
                select(AnonymousVoteSession)
                .where(AnonymousVoteSession.id == self.session_id)
                .options(
                    selectinload(AnonymousVoteSession.candidates),
                    selectinload(AnonymousVoteSession.ballots),
                )
            )
            poll_embed = build_poll_embed(
                loaded,
                list(loaded.candidates),
                list(loaded.ballots),
            ) if loaded else None

        label = "Approve" if choice == CHOICE_APPROVE else "Reject"
        await interaction.response.send_message(
            f"Vote {action}: **{label}** for **{display_name}**. "
            "Your choice is anonymous; only a neutral activity box is shown publicly.",
            ephemeral=True,
        )

        if poll_embed is not None and interaction.message is not None:
            try:
                await interaction.message.edit(embed=poll_embed)
            except discord.HTTPException:
                logger.exception(
                    "Failed to refresh poll embed for session %s after vote.",
                    self.session_id,
                )


async def close_anonymous_vote(bot: Bot, session_id: int) -> None:
    """Close a vote session, post totals, and disable controls."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(AnonymousVoteSession)
            .where(AnonymousVoteSession.id == session_id)
            .options(
                selectinload(AnonymousVoteSession.candidates),
                selectinload(AnonymousVoteSession.ballots),
            )
        )
        vote_session = await session.scalar(stmt)
        if not vote_session:
            logger.warning("Anonymous vote session %s not found for close.", session_id)
            return
        if vote_session.closed:
            logger.debug("Anonymous vote session %s already closed.", session_id)
            return

        vote_session.closed = True
        candidates = list(vote_session.candidates)
        ballots = list(vote_session.ballots)
        channel_id = vote_session.channel_id
        message_id = vote_session.message_id
        results_embed = build_results_embed(vote_session, candidates, ballots)
        await session.commit()

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            logger.exception("Failed to fetch channel %s for vote session %s", channel_id, session_id)
            return

    view = AnonymousVoteView(session_id, bot, candidates)
    for item in view.children:
        item.disabled = True

    if message_id:
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(
                content="This anonymous vote is closed. Results below.",
                embed=results_embed,
                view=view,
            )
            return
        except discord.HTTPException:
            logger.exception(
                "Failed to edit poll message %s for session %s; posting results separately.",
                message_id,
                session_id,
            )

    await channel.send(embed=results_embed)


def schedule_vote_close(bot: Bot, session_id: int, closes_at: datetime) -> None:
    """Schedule auto-close for a vote session on the bot event loop."""
    bot.loop.create_task(schedule(close_anonymous_vote(bot, session_id), closes_at))


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

    now = datetime.now()
    for vote_session in open_sessions:
        bot.add_view(AnonymousVoteView(vote_session.id, bot, vote_session.candidates))
        if vote_session.closes_at <= now:
            bot.loop.create_task(close_anonymous_vote(bot, vote_session.id))
        else:
            schedule_vote_close(bot, vote_session.id, vote_session.closes_at)

    if open_sessions:
        logger.info("Registered %d open anonymous vote session(s).", len(open_sessions))
