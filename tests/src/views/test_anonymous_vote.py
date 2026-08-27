from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ui import Button, Select

from src.core import settings
from src.views.anonymous_vote import (
    CHOICE_APPROVE,
    CHOICE_REJECT,
    MAX_ACTIVITY_BOXES_PER_NOMINEE,
    VOTE_ACTIVITY_BOX,
    AnonymousVoteView,
    BallotView,
    _ballot_counts_by_candidate,
    _format_nominee_line,
    build_poll_embed,
    build_results_embed,
    close_anonymous_vote,
    register_anonymous_vote_views,
    schedule_vote_close,
)
from tests import helpers


def _make_session(
    session_id: int = 1,
    topic: str | None = "Promotion round",
    closes_at: int = 1800000000,
    closed: bool = False,
    message_id: int | None = 666,
) -> MagicMock:
    """Build a mock AnonymousVoteSession model instance."""
    session = MagicMock()
    session.id = session_id
    session.topic = topic
    session.closes_at = closes_at
    session.closed = closed
    session.channel_id = 555
    session.message_id = message_id
    return session


def _make_candidate(candidate_id: int = 1, session_id: int = 1, name: str = "Nominee") -> MagicMock:
    """Build a mock AnonymousVoteCandidate model instance."""
    candidate = MagicMock()
    candidate.id = candidate_id
    candidate.session_id = session_id
    candidate.user_id = 100 + candidate_id
    candidate.display_name = name
    return candidate


def _make_ballot(candidate_id: int = 1, choice: str = CHOICE_APPROVE) -> MagicMock:
    """Build a mock AnonymousVoteBallot model instance."""
    ballot = MagicMock()
    ballot.candidate_id = candidate_id
    ballot.choice = choice
    return ballot


def _session_ctx(session_mock: AsyncMock) -> MagicMock:
    """Wrap an AsyncMock session so it works as ``async with AsyncSessionLocal() as s``."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=session_mock)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _make_voter(can_vote: bool = True) -> helpers.MockMember:
    """Build a member who does or does not hold a VOTE_CASTERS role."""
    role_id = settings.role_groups["VOTE_CASTERS"][0] if can_vote else 999999
    return helpers.MockMember(roles=[helpers.MockRole(name="Voter", id=role_id)])


def _make_interaction(
    values: list[str] | None = None,
    user: helpers.MockMember | None = None,
    message: MagicMock | None = None,
) -> MagicMock:
    """Build a lightweight mock Interaction with the attributes our callbacks use."""
    interaction = MagicMock()
    interaction.user = user or _make_voter()
    interaction.data = {"values": list(values or [])}

    interaction.response = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()

    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()

    interaction.message = MagicMock() if message is None else message
    interaction.message.edit = AsyncMock()
    return interaction


def _loaded_session(session_id: int = 1, message_id: int | None = 666) -> MagicMock:
    """Build the eagerly-loaded session the poll embed is rebuilt from."""
    loaded = _make_session(session_id=session_id, message_id=message_id)
    loaded.candidates = [_make_candidate(session_id=session_id)]
    loaded.ballots = []
    return loaded


def _make_poll_message() -> MagicMock:
    """Build the public poll message a ballot writes its refreshed embed back to."""
    message = MagicMock()
    message.edit = AsyncMock()
    return message


def _mysql_dialect() -> object:
    """The dialect the upsert is compiled against; ``on_duplicate_key_update`` is MySQL-only."""
    from sqlalchemy.dialects import mysql

    return mysql.dialect()


def _close_db(rowcount: int = 1, loaded: MagicMock | None = None) -> AsyncMock:
    """Session mock for close; *rowcount* decides whether this coroutine claims the close."""
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(rowcount=rowcount))
    session.scalar = AsyncMock(return_value=loaded)
    return session


def _open_session_db(candidate: MagicMock, vote_session: MagicMock | None = None) -> AsyncMock:
    """Build a session mock whose ``get`` resolves the vote session then the candidate."""
    session = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock(side_effect=[vote_session or _make_session(), candidate])
    return session


class TestBuildPollEmbed:
    def test_closes_field_renders_epoch_seconds_directly(self):
        session = _make_session(closes_at=1800000000)
        embed = build_poll_embed(session, [_make_candidate()])

        closes_field = next(f for f in embed.fields if f.name == "Closes")
        assert closes_field.value == "<t:1800000000:F> (<t:1800000000:R>)"


class TestAnonymousVoteViewShape:
    @pytest.mark.asyncio
    async def test_holds_only_the_select(self, bot):
        view = AnonymousVoteView(9, bot, [_make_candidate(session_id=9)])

        assert [type(c) for c in view.children] == [Select]
        assert view.children[0].custom_id == "anon_vote_select:9"
        assert view.timeout is None

    @pytest.mark.asyncio
    async def test_module_keeps_no_pending_selection_state(self):
        import src.views.anonymous_vote as module

        assert not hasattr(module, "_pending_selection")


class TestSelectCallback:
    @pytest.mark.asyncio
    async def test_reads_nominee_from_interaction_payload_not_shared_item(self, bot):
        """Two concurrent voters must not cross nominees via the shared Select item."""
        candidates = [
            _make_candidate(candidate_id=1, session_id=9, name="Alice"),
            _make_candidate(candidate_id=2, session_id=9, name="Bob"),
        ]
        view = AnonymousVoteView(9, bot, candidates)

        # py-cord's ViewStore.dispatch calls refresh_state on the shared item per
        # interaction and the callback runs in a later task, so by the time Alice's
        # callback runs the item can already hold Bob's selection.
        bobs_interaction = _make_interaction(values=["2"])
        view.children[0]._selected_values = ["2"]
        view.children[0]._interaction = bobs_interaction
        assert view.children[0].values == ["2"]

        by_id = {c.id: c for c in candidates}
        session = AsyncMock()
        session.get = AsyncMock(side_effect=lambda model, pk: _make_session() if pk == 9 else by_id.get(pk))

        interaction = _make_interaction(values=["1"])
        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await view.children[0].callback(interaction)

        ballot = interaction.followup.send.call_args.kwargs["view"]
        assert ballot.candidate_id == 1
        assert "Alice" in interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_sends_ephemeral_ballot_view_for_the_chosen_nominee(self, bot):
        candidate = _make_candidate(candidate_id=5, session_id=9, name="Carol")
        view = AnonymousVoteView(9, bot, [candidate])

        poll_message = MagicMock()
        interaction = _make_interaction(values=["5"], message=poll_message)
        session = _open_session_db(candidate)

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await view.children[0].callback(interaction)

        kwargs = interaction.followup.send.call_args.kwargs
        assert kwargs["ephemeral"] is True
        ballot = kwargs["view"]
        assert isinstance(ballot, BallotView)
        assert (ballot.session_id, ballot.candidate_id) == (9, 5)
        assert ballot.poll_message is poll_message

    @pytest.mark.asyncio
    async def test_defers_before_touching_the_database(self, bot):
        candidate = _make_candidate(candidate_id=5, session_id=9)
        view = AnonymousVoteView(9, bot, [candidate])

        order: list[str] = []
        interaction = _make_interaction(values=["5"])
        interaction.response.defer = AsyncMock(side_effect=lambda **kw: order.append("defer"))

        session = _open_session_db(candidate)
        session_ctx = _session_ctx(session)

        def open_session() -> MagicMock:
            order.append("db")
            return session_ctx

        with patch("src.views.anonymous_vote.AsyncSessionLocal", side_effect=open_session):
            await view.children[0].callback(interaction)

        assert order == ["defer", "db"]
        interaction.response.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_rejects_a_member_without_a_voter_role(self, bot):
        view = AnonymousVoteView(9, bot, [_make_candidate(session_id=9)])
        interaction = _make_interaction(values=["1"], user=_make_voter(can_vote=False))

        with patch("src.views.anonymous_vote.AsyncSessionLocal") as session_local:
            await view.children[0].callback(interaction)

        session_local.assert_not_called()
        assert "not authorized" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_reports_a_closed_poll(self, bot):
        view = AnonymousVoteView(9, bot, [_make_candidate(session_id=9)])
        interaction = _make_interaction(values=["1"])
        session = _open_session_db(None, vote_session=_make_session(closed=True))

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await view.children[0].callback(interaction)

        assert interaction.followup.send.call_args[0][0] == "This poll is closed."

    @pytest.mark.asyncio
    async def test_reports_a_nominee_from_another_session(self, bot):
        view = AnonymousVoteView(9, bot, [_make_candidate(session_id=9)])
        interaction = _make_interaction(values=["1"])
        session = _open_session_db(_make_candidate(candidate_id=1, session_id=77))

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await view.children[0].callback(interaction)

        assert interaction.followup.send.call_args[0][0] == "Unknown nominee."

    @pytest.mark.asyncio
    async def test_reports_an_empty_selection_without_deferring(self, bot):
        view = AnonymousVoteView(9, bot, [_make_candidate(session_id=9)])
        interaction = _make_interaction(values=[])

        with patch("src.views.anonymous_vote.AsyncSessionLocal") as session_local:
            await view.children[0].callback(interaction)

        session_local.assert_not_called()
        interaction.response.defer.assert_not_awaited()
        assert interaction.response.send_message.call_args[0][0] == "No nominee selected."
        assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True

    @pytest.mark.asyncio
    async def test_reports_a_payload_carrying_no_values_key(self, bot):
        view = AnonymousVoteView(9, bot, [_make_candidate(session_id=9)])
        interaction = _make_interaction()
        interaction.data = {}

        with patch("src.views.anonymous_vote.AsyncSessionLocal") as session_local:
            await view.children[0].callback(interaction)

        session_local.assert_not_called()
        interaction.response.defer.assert_not_awaited()
        assert interaction.response.send_message.call_args[0][0] == "No nominee selected."


class TestBallotView:
    @pytest.mark.asyncio
    async def test_holds_two_buttons_and_is_not_persistent(self):
        ballot = BallotView(9, 5, _make_poll_message())

        buttons = [c for c in ballot.children if isinstance(c, Button)]
        assert [b.label for b in buttons] == ["Approve", "Reject"]
        assert ballot.is_persistent() is False

    @pytest.mark.asyncio
    async def test_upserts_the_ballot_instead_of_read_then_insert(self):
        candidate = _make_candidate(candidate_id=5, session_id=9, name="Carol")
        session = _open_session_db(candidate)
        session.scalar = AsyncMock(return_value=_loaded_session())

        ballot = BallotView(9, 5, _make_poll_message())
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.add.assert_not_called()
        stmt = session.execute.await_args.args[0]
        assert stmt.is_insert
        compiled = str(stmt.compile(dialect=_mysql_dialect()))
        assert "ON DUPLICATE KEY UPDATE" in compiled

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("rowcount", "expected_wording"),
        [(2, "Vote updated"), (1, "Vote recorded")],
    )
    async def test_wording_reflects_whether_the_stored_choice_changed(self, rowcount, expected_wording):
        """Only rowcount 2 proves a change; 1 is insert-or-same-value through asyncmy."""
        candidate = _make_candidate(candidate_id=5, session_id=9, name="Carol")
        session = _open_session_db(candidate)
        session.execute = AsyncMock(return_value=MagicMock(rowcount=rowcount))
        session.scalar = AsyncMock(return_value=_loaded_session())

        ballot = BallotView(9, 5, _make_poll_message())
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        assert expected_wording in interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_refuses_a_voter_who_lost_the_role_since_the_ballot_was_issued(self):
        """The ballot outlives the role check that issued it, so re-check at cast time."""
        session = AsyncMock()
        ballot = BallotView(9, 5, _make_poll_message())
        interaction = _make_interaction(user=_make_voter(can_vote=False))

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)) as db:
            await ballot.children[0].callback(interaction)

        db.assert_not_called()
        session.execute.assert_not_awaited()
        assert "not authorized" in interaction.response.send_message.call_args[0][0]

    @pytest.mark.asyncio
    async def test_still_accepts_a_voter_who_kept_the_role(self):
        candidate = _make_candidate(candidate_id=5, session_id=9, name="Carol")
        session = _open_session_db(candidate)
        session.scalar = AsyncMock(return_value=_loaded_session())

        ballot = BallotView(9, 5, _make_poll_message())
        interaction = _make_interaction(user=_make_voter(can_vote=True))

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.execute.assert_awaited_once()
        assert "Carol" in interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_timeout_expires_before_the_interaction_token_does(self):
        """The clock starts after the send returns, so 900 would fire past token expiry."""
        assert BallotView(9, 5, None).timeout == 840

    @pytest.mark.asyncio
    async def test_on_timeout_disables_the_ballot_and_says_it_lapsed(self):
        message = _make_poll_message()
        ballot = BallotView(9, 5, _make_poll_message())
        ballot.message = message

        await ballot.on_timeout()

        assert all(item.disabled for item in ballot.children)
        assert "expired" in message.edit.await_args.kwargs["content"]
        assert message.edit.await_args.kwargs["view"] is ballot

    @pytest.mark.asyncio
    async def test_on_timeout_without_a_message_does_not_raise(self):
        ballot = BallotView(9, 5, _make_poll_message())
        ballot.message = None

        await ballot.on_timeout()

        assert all(item.disabled for item in ballot.children)

    @pytest.mark.asyncio
    async def test_on_timeout_survives_a_failed_edit(self):
        message = _make_poll_message()
        message.edit = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "gone"))
        ballot = BallotView(9, 5, _make_poll_message())
        ballot.message = message

        await ballot.on_timeout()

        message.edit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reports_a_vanished_session_instead_of_crashing_after_the_write(self):
        """The ballot is already persisted here; an AttributeError would strand the voter."""
        candidate = _make_candidate(candidate_id=5, session_id=9, name="Carol")
        session = _open_session_db(candidate)
        session.scalar = AsyncMock(return_value=None)

        ballot = BallotView(9, 5, _make_poll_message())
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("button_index", "expected"), [(0, CHOICE_APPROVE), (1, CHOICE_REJECT)])
    async def test_each_button_records_its_own_choice(self, button_index, expected):
        candidate = _make_candidate(candidate_id=5, session_id=9, name="Carol")
        session = _open_session_db(candidate)
        session.scalar = AsyncMock(return_value=_loaded_session())

        ballot = BallotView(9, 5, _make_poll_message())
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[button_index].callback(interaction)

        params = session.execute.await_args.args[0].compile(dialect=_mysql_dialect()).params
        assert params["choice"] == expected
        assert expected.capitalize() in interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_defers_before_touching_the_database(self):
        candidate = _make_candidate(candidate_id=5, session_id=9)
        session = _open_session_db(candidate)
        session.scalar = AsyncMock(return_value=_loaded_session())

        order: list[str] = []
        interaction = _make_interaction()
        interaction.response.defer = AsyncMock(side_effect=lambda **kw: order.append("defer"))
        session_ctx = _session_ctx(session)

        def open_session() -> MagicMock:
            order.append("db")
            return session_ctx

        ballot = BallotView(9, 5, _make_poll_message())
        with patch("src.views.anonymous_vote.AsyncSessionLocal", side_effect=open_session):
            await ballot.children[0].callback(interaction)

        assert order == ["defer", "db"]
        interaction.response.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_refreshes_the_public_poll_message(self):
        candidate = _make_candidate(candidate_id=5, session_id=9)
        session = _open_session_db(candidate)
        session.scalar = AsyncMock(return_value=_loaded_session())

        poll_message = MagicMock()
        poll_message.edit = AsyncMock()
        ballot = BallotView(9, 5, poll_message)

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(_make_interaction())

        poll_message.edit.assert_awaited_once()
        assert "embed" in poll_message.edit.await_args.kwargs

    @pytest.mark.asyncio
    async def test_records_the_vote_when_there_is_no_poll_message_to_refresh(self):
        candidate = _make_candidate(candidate_id=5, session_id=9, name="Carol")
        session = _open_session_db(candidate)
        session.scalar = AsyncMock(return_value=_loaded_session())

        ballot = BallotView(9, 5, None)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.execute.assert_awaited_once()
        assert "Carol" in interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_a_failed_refresh_does_not_lose_the_recorded_vote(self):
        candidate = _make_candidate(candidate_id=5, session_id=9, name="Carol")
        session = _open_session_db(candidate)
        session.scalar = AsyncMock(return_value=_loaded_session())

        poll_message = _make_poll_message()
        poll_message.edit = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "boom"))

        ballot = BallotView(9, 5, poll_message)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.execute.assert_awaited_once()
        assert "Carol" in interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_reports_a_closed_poll_without_writing(self):
        session = _open_session_db(None, vote_session=_make_session(closed=True))
        poll_message = MagicMock()
        poll_message.edit = AsyncMock()

        ballot = BallotView(9, 5, poll_message)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.execute.assert_not_awaited()
        poll_message.edit.assert_not_awaited()
        assert interaction.followup.send.call_args[0][0] == "This poll is closed."

    @pytest.mark.asyncio
    async def test_reports_a_missing_nominee_without_writing(self):
        session = _open_session_db(None)
        poll_message = _make_poll_message()

        ballot = BallotView(9, 5, poll_message)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.execute.assert_not_awaited()
        poll_message.edit.assert_not_awaited()
        assert interaction.followup.send.call_args[0][0] == "Unknown nominee."

    @pytest.mark.asyncio
    async def test_reports_a_nominee_from_another_session_without_writing(self):
        """A ballot must not write against a candidate row belonging to a different poll."""
        session = _open_session_db(_make_candidate(candidate_id=5, session_id=77))
        poll_message = _make_poll_message()

        ballot = BallotView(9, 5, poll_message)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.execute.assert_not_awaited()
        poll_message.edit.assert_not_awaited()
        assert interaction.followup.send.call_args[0][0] == "Unknown nominee."


class TestCloseAnonymousVote:
    @pytest.mark.asyncio
    async def test_disables_the_select_and_posts_results(self, bot):
        session = _close_db(loaded=_loaded_session(session_id=9))

        message = _make_poll_message()
        channel = MagicMock()
        channel.fetch_message = AsyncMock(return_value=message)
        bot.get_channel = MagicMock(return_value=channel)

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        session.execute.assert_awaited_once()
        view = message.edit.await_args.kwargs["view"]
        assert all(item.disabled for item in view.children)

    @pytest.mark.asyncio
    async def test_a_failed_fallback_send_is_logged_not_raised(self, bot):
        """close runs in a bare task, so an unhandled send failure would vanish silently."""
        session = _close_db(loaded=_loaded_session(session_id=9, message_id=None))

        channel = MagicMock()
        channel.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "no perms"))
        bot.get_channel = MagicMock(return_value=channel)

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        channel.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_failed_edit_falls_back_to_a_new_message(self, bot):
        session = _close_db(loaded=_loaded_session(session_id=9, message_id=666))

        channel = MagicMock()
        channel.fetch_message = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "gone"))
        channel.send = AsyncMock()
        bot.get_channel = MagicMock(return_value=channel)

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        channel.send.assert_awaited_once()
        assert channel.send.await_args.kwargs["embed"] is not None

    @pytest.mark.asyncio
    async def test_gives_up_when_the_channel_cannot_be_resolved(self, bot):
        session = _close_db(loaded=_loaded_session(session_id=9))

        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "nope"))

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        bot.fetch_channel.assert_awaited_once_with(555)

    @pytest.mark.asyncio
    async def test_claims_the_close_with_a_conditional_update(self, bot):
        """on_ready re-schedules a close on every reconnect, so closes pile up and race."""
        session = _close_db(loaded=_loaded_session(session_id=9))

        message = _make_poll_message()
        channel = MagicMock()
        channel.fetch_message = AsyncMock(return_value=message)
        bot.get_channel = MagicMock(return_value=channel)

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        stmt = session.execute.await_args.args[0]
        assert stmt.is_update
        compiled = str(stmt.compile(dialect=_mysql_dialect()))
        assert "closed is false" in compiled.lower()
        message.edit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_losing_concurrent_close_publishes_nothing(self, bot):
        """Second coroutine's UPDATE matches no row, so it must not post results twice."""
        session = _close_db(rowcount=0, loaded=_loaded_session(session_id=9))
        bot.get_channel = MagicMock()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        bot.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_a_close_it_did_not_claim(self, bot):
        """Already closed and already deleted are one case: the UPDATE matched no row."""
        session = _close_db(rowcount=0)
        bot.get_channel = MagicMock()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        bot.get_channel.assert_not_called()

    @pytest.mark.asyncio
    async def test_publishes_nothing_when_the_row_vanishes_after_the_claim(self, bot):
        """Claimed the close, then the re-SELECT found nothing; must not crash the task."""
        session = _close_db(rowcount=1, loaded=None)
        bot.get_channel = MagicMock()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        bot.get_channel.assert_not_called()


class TestScheduleVoteClose:
    @pytest.mark.asyncio
    async def test_converts_epoch_seconds_to_datetime(self, bot):
        with (
            patch("src.views.anonymous_vote.schedule") as mock_schedule,
            patch("src.views.anonymous_vote.close_anonymous_vote", new_callable=MagicMock),
        ):
            schedule_vote_close(bot, 7, 1800000000)

        mock_schedule.assert_called_once()
        assert mock_schedule.call_args[0][1] == datetime.fromtimestamp(1800000000)


class TestRegisterAnonymousVoteViews:
    @pytest.mark.asyncio
    async def test_schedules_close_for_future_session(self, bot):
        vote_session = _make_session(session_id=3, closes_at=1800000000)
        vote_session.candidates = [_make_candidate(session_id=3)]

        scalars_result = MagicMock()
        scalars_result.all.return_value = [vote_session]
        session = AsyncMock()
        session.scalars = AsyncMock(return_value=scalars_result)

        with (
            patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)),
            patch("src.views.anonymous_vote.schedule_vote_close") as mock_schedule_close,
        ):
            await register_anonymous_vote_views(bot)

        mock_schedule_close.assert_called_once_with(bot, 3, 1800000000)
        bot.add_view.assert_called_once()

    @pytest.mark.asyncio
    async def test_closes_expired_session_immediately(self, bot):
        vote_session = _make_session(session_id=4, closes_at=1000000000)
        vote_session.candidates = []

        scalars_result = MagicMock()
        scalars_result.all.return_value = [vote_session]
        session = AsyncMock()
        session.scalars = AsyncMock(return_value=scalars_result)

        with (
            patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)),
            patch("src.views.anonymous_vote.schedule_vote_close") as mock_schedule_close,
            patch("src.views.anonymous_vote.close_anonymous_vote") as mock_close,
        ):
            await register_anonymous_vote_views(bot)

        mock_schedule_close.assert_not_called()
        mock_close.assert_called_once_with(bot, 4)


class TestBallotCountsByCandidate:
    def test_counts_each_candidates_ballots_separately(self):
        ballots = [
            _make_ballot(candidate_id=1),
            _make_ballot(candidate_id=2),
            _make_ballot(candidate_id=1),
            _make_ballot(candidate_id=3),
            _make_ballot(candidate_id=1),
            _make_ballot(candidate_id=2),
        ]

        counts = _ballot_counts_by_candidate(ballots)

        assert counts[1] == 3
        assert counts[2] == 2
        assert counts[3] == 1

    def test_a_candidate_with_no_ballots_is_absent_and_reads_as_zero(self):
        counts = _ballot_counts_by_candidate([_make_ballot(candidate_id=1)])

        assert 2 not in counts
        assert counts.get(2, 0) == 0
        assert counts.get(1, 0) == 1

    def test_no_ballots_counts_nothing(self):
        assert _ballot_counts_by_candidate([]) == {}


class TestFormatNomineeLine:
    def test_no_ballots_renders_the_bare_nominee_line(self):
        line = _format_nominee_line(_make_candidate(candidate_id=3, name="Carol"), 0)

        assert line == "• **Carol** (`103`)"

    def test_a_single_ballot_renders_one_box(self):
        line = _format_nominee_line(_make_candidate(candidate_id=3, name="Carol"), 1)

        assert line == "• **Carol** (`103`) ⬜"

    def test_several_ballots_render_one_box_each(self):
        line = _format_nominee_line(_make_candidate(candidate_id=3, name="Carol"), 4)

        assert line == "• **Carol** (`103`) ⬜⬜⬜⬜"

    def test_exactly_the_maximum_is_not_marked_as_truncated(self):
        line = _format_nominee_line(_make_candidate(), MAX_ACTIVITY_BOXES_PER_NOMINEE)

        assert line.count(VOTE_ACTIVITY_BOX) == 40
        assert "…" not in line

    def test_one_over_the_maximum_caps_the_boxes_and_marks_truncation(self):
        line = _format_nominee_line(_make_candidate(), MAX_ACTIVITY_BOXES_PER_NOMINEE + 1)

        assert line.count(VOTE_ACTIVITY_BOX) == 40
        assert line.endswith("…")

    def test_far_over_the_maximum_still_caps_at_the_maximum(self):
        line = _format_nominee_line(_make_candidate(), 500)

        assert line.count(VOTE_ACTIVITY_BOX) == 40
        assert line.endswith("…")


class TestBuildResultsEmbed:
    def test_tallies_approvals_and_rejections_per_nominee(self):
        candidates = [
            _make_candidate(candidate_id=1, name="Alice"),
            _make_candidate(candidate_id=2, name="Bob"),
        ]
        ballots = [
            _make_ballot(candidate_id=1, choice=CHOICE_APPROVE),
            _make_ballot(candidate_id=1, choice=CHOICE_APPROVE),
            _make_ballot(candidate_id=1, choice=CHOICE_REJECT),
            _make_ballot(candidate_id=2, choice=CHOICE_REJECT),
            _make_ballot(candidate_id=2, choice=CHOICE_REJECT),
        ]

        embed = build_results_embed(_make_session(), candidates, ballots)

        assert "• **Alice** — ✓ 2 / ✗ 1" in embed.description
        assert "• **Bob** — ✓ 0 / ✗ 2" in embed.description

    def test_a_nominee_with_no_ballots_tallies_zero_both_ways(self):
        candidates = [
            _make_candidate(candidate_id=1, name="Alice"),
            _make_candidate(candidate_id=2, name="Bob"),
        ]
        ballots = [_make_ballot(candidate_id=1, choice=CHOICE_APPROVE)]

        embed = build_results_embed(_make_session(), candidates, ballots)

        assert "• **Alice** — ✓ 1 / ✗ 0" in embed.description
        assert "• **Bob** — ✓ 0 / ✗ 0" in embed.description

    def test_ignores_a_ballot_whose_choice_is_neither_approve_nor_reject(self):
        candidate = _make_candidate(candidate_id=1, name="Alice")
        ballots = [
            _make_ballot(candidate_id=1, choice=CHOICE_APPROVE),
            _make_ballot(candidate_id=1, choice="abstain"),
            _make_ballot(candidate_id=1, choice=""),
        ]

        embed = build_results_embed(_make_session(), [candidate], ballots)

        assert "• **Alice** — ✓ 1 / ✗ 0" in embed.description
