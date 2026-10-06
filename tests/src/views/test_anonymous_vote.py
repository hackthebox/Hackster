from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ui import Button, Select

from src.core import settings
import src.views.anonymous_vote as anonymous_vote
from src.views.anonymous_vote import (
    CHOICE_APPROVE,
    CHOICE_REJECT,
    AnonymousVoteView,
    BallotView,
    build_poll_embed,
    build_results_embed,
    close_anonymous_vote,
    publish_vote_results,
    register_anonymous_vote_views,
    schedule_vote_close,
    voter_hash,
)
from tests import helpers

VOTER_ID = 900000000000000001


@pytest.fixture(autouse=True)
def reset_module_state():
    """The close-task registry and publish guard are module globals; keep tests independent."""
    anonymous_vote._close_tasks.clear()
    anonymous_vote._publishing.clear()
    yield
    anonymous_vote._close_tasks.clear()
    anonymous_vote._publishing.clear()


def _make_session(
    session_id: int = 1,
    topic: str | None = "Promotion round",
    closes_at: int = 1800000000,
    closed: bool = False,
    message_id: int | None = 666,
    published_at: int | None = None,
) -> MagicMock:
    """Build a mock AnonymousVoteSession model instance."""
    session = MagicMock()
    session.id = session_id
    session.topic = topic
    session.closes_at = closes_at
    session.closed = closed
    session.channel_id = 555
    session.message_id = message_id
    session.published_at = published_at
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


def _make_voter(can_vote: bool = True, user_id: int = VOTER_ID) -> helpers.MockMember:
    """Build a member who does or does not hold a VOTE_CASTERS role.

    The id is fixed so it can never collide with a nominee's user_id and trip the self-vote check.
    """
    role_id = settings.role_groups["VOTE_CASTERS"][0] if can_vote else 999999
    return helpers.MockMember(id=user_id, roles=[helpers.MockRole(name="Voter", id=role_id)])


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
    """Build the public poll message that close edits the results into."""
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

    def test_lists_nominees_without_any_vote_activity(self):
        """A live per-nominee marker shows who voted and when, so the poll shows nothing until close."""
        embed = build_poll_embed(_make_session(), [_make_candidate(candidate_id=3, name="Carol")])

        assert embed.description == "• **Carol** (`103`)"

    def test_escapes_markdown_in_nominee_names(self):
        candidate = _make_candidate(name="[click](https://example.com) **bold**")

        embed = build_poll_embed(_make_session(), [candidate])

        # A leading backslash on "[" is what stops Discord rendering the masked link.
        assert "\\[click](https://example.com)" in embed.description
        assert "\\*\\*bold\\*\\*" in embed.description

    def test_does_not_promise_more_anonymity_than_it_gives(self):
        how_to = next(f for f in build_poll_embed(_make_session(), []).fields if f.name == "How to vote")

        assert "keyed hash" in how_to.value


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

    @pytest.mark.asyncio
    async def test_reports_a_payload_with_no_data(self, bot):
        view = AnonymousVoteView(9, bot, [_make_candidate(session_id=9)])
        interaction = _make_interaction()
        interaction.data = None

        with patch("src.views.anonymous_vote.AsyncSessionLocal") as session_local:
            await view.children[0].callback(interaction)

        session_local.assert_not_called()
        assert interaction.response.send_message.call_args[0][0] == "No nominee selected."

    @pytest.mark.asyncio
    async def test_reports_a_non_numeric_value_before_deferring(self, bot):
        """A ValueError after the defer would leave the voter with no answer at all."""
        view = AnonymousVoteView(9, bot, [_make_candidate(session_id=9)])
        interaction = _make_interaction(values=["not-a-number"])

        with patch("src.views.anonymous_vote.AsyncSessionLocal") as session_local:
            await view.children[0].callback(interaction)

        session_local.assert_not_called()
        interaction.response.defer.assert_not_awaited()
        assert interaction.response.send_message.call_args[0][0] == "Unknown nominee."

    @pytest.mark.asyncio
    async def test_refuses_a_ballot_on_yourself(self, bot):
        candidate = _make_candidate(candidate_id=5, session_id=9)
        view = AnonymousVoteView(9, bot, [candidate])
        interaction = _make_interaction(values=["5"], user=_make_voter(user_id=candidate.user_id))
        session = _open_session_db(candidate)

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await view.children[0].callback(interaction)

        assert interaction.followup.send.call_args[0][0] == "You can't vote on yourself."
        assert "view" not in interaction.followup.send.call_args.kwargs


class TestBallotView:
    @pytest.mark.asyncio
    async def test_holds_two_buttons_and_is_not_persistent(self):
        ballot = BallotView(9, 5)

        buttons = [c for c in ballot.children if isinstance(c, Button)]
        assert [b.label for b in buttons] == ["Approve", "Reject"]
        assert ballot.is_persistent() is False

    @pytest.mark.asyncio
    async def test_upserts_the_ballot_instead_of_read_then_insert(self):
        candidate = _make_candidate(candidate_id=5, session_id=9, name="Carol")
        session = _open_session_db(candidate)

        ballot = BallotView(9, 5)
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

        ballot = BallotView(9, 5)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        assert expected_wording in interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_refuses_a_voter_who_lost_the_role_since_the_ballot_was_issued(self):
        """The ballot outlives the role check that issued it, so re-check at cast time."""
        session = AsyncMock()
        ballot = BallotView(9, 5)
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

        ballot = BallotView(9, 5)
        interaction = _make_interaction(user=_make_voter(can_vote=True))

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.execute.assert_awaited_once()
        assert "Carol" in interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_timeout_expires_before_the_interaction_token_does(self):
        """The clock starts after the send returns, so 900 would fire past token expiry."""
        assert BallotView(9, 5).timeout == 840

    @pytest.mark.asyncio
    async def test_on_timeout_disables_the_ballot_and_says_it_lapsed(self):
        message = _make_poll_message()
        ballot = BallotView(9, 5)
        ballot.message = message

        await ballot.on_timeout()

        assert all(item.disabled for item in ballot.children)
        assert "expired" in message.edit.await_args.kwargs["content"]
        assert message.edit.await_args.kwargs["view"] is ballot

    @pytest.mark.asyncio
    async def test_on_timeout_without_a_message_does_not_raise(self):
        ballot = BallotView(9, 5)
        ballot.message = None

        await ballot.on_timeout()

        assert all(item.disabled for item in ballot.children)

    @pytest.mark.asyncio
    async def test_on_timeout_survives_a_failed_edit(self):
        message = _make_poll_message()
        message.edit = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "gone"))
        ballot = BallotView(9, 5)
        ballot.message = message

        await ballot.on_timeout()

        message.edit.assert_awaited_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(("button_index", "expected"), [(0, CHOICE_APPROVE), (1, CHOICE_REJECT)])
    async def test_each_button_records_its_own_choice(self, button_index, expected):
        candidate = _make_candidate(candidate_id=5, session_id=9, name="Carol")
        session = _open_session_db(candidate)

        ballot = BallotView(9, 5)
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

        order: list[str] = []
        interaction = _make_interaction()
        interaction.response.defer = AsyncMock(side_effect=lambda **kw: order.append("defer"))
        session_ctx = _session_ctx(session)

        def open_session() -> MagicMock:
            order.append("db")
            return session_ctx

        ballot = BallotView(9, 5)
        with patch("src.views.anonymous_vote.AsyncSessionLocal", side_effect=open_session):
            await ballot.children[0].callback(interaction)

        assert order == ["defer", "db"]
        interaction.response.send_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_casting_a_vote_leaves_the_public_poll_alone(self):
        """Redrawing the poll per ballot told the channel who voted and when."""
        candidate = _make_candidate(candidate_id=5, session_id=9)
        session = _open_session_db(candidate)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await BallotView(9, 5).children[0].callback(interaction)

        session.execute.assert_awaited_once()
        interaction.message.edit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stores_a_keyed_hash_instead_of_the_voter_id(self):
        candidate = _make_candidate(candidate_id=5, session_id=9)
        session = _open_session_db(candidate)

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await BallotView(9, 5).children[0].callback(_make_interaction())

        params = session.execute.await_args.args[0].compile(dialect=_mysql_dialect()).params
        assert params["voter_hash"] == voter_hash(9, VOTER_ID)
        assert str(VOTER_ID) not in str(params)

    @pytest.mark.asyncio
    async def test_refuses_a_ballot_on_yourself_without_writing(self):
        """Checked at write time too, in case the ballot was obtained some other way."""
        candidate = _make_candidate(candidate_id=5, session_id=9)
        session = _open_session_db(candidate)
        interaction = _make_interaction(user=_make_voter(user_id=candidate.user_id))

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await BallotView(9, 5).children[0].callback(interaction)

        session.execute.assert_not_awaited()
        assert interaction.followup.send.call_args[0][0] == "You can't vote on yourself."

    @pytest.mark.asyncio
    async def test_escapes_markdown_in_the_confirmation(self):
        candidate = _make_candidate(candidate_id=5, session_id=9, name="**Carol**")
        session = _open_session_db(candidate)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await BallotView(9, 5).children[0].callback(interaction)

        assert "\\*\\*Carol\\*\\*" in interaction.followup.send.call_args[0][0]

    @pytest.mark.asyncio
    async def test_reports_a_closed_poll_without_writing(self):
        session = _open_session_db(None, vote_session=_make_session(closed=True))

        ballot = BallotView(9, 5)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.execute.assert_not_awaited()
        assert interaction.followup.send.call_args[0][0] == "This poll is closed."

    @pytest.mark.asyncio
    async def test_reports_a_missing_nominee_without_writing(self):
        session = _open_session_db(None)

        ballot = BallotView(9, 5)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.execute.assert_not_awaited()
        assert interaction.followup.send.call_args[0][0] == "Unknown nominee."

    @pytest.mark.asyncio
    async def test_reports_a_nominee_from_another_session_without_writing(self):
        """A ballot must not write against a candidate row belonging to a different poll."""
        session = _open_session_db(_make_candidate(candidate_id=5, session_id=77))

        ballot = BallotView(9, 5)
        interaction = _make_interaction()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await ballot.children[0].callback(interaction)

        session.execute.assert_not_awaited()
        assert interaction.followup.send.call_args[0][0] == "Unknown nominee."


def _compiled(stmt) -> str:
    return str(stmt.compile(dialect=_mysql_dialect())).lower()


def _scalars(*results: list) -> AsyncMock:
    """``session.scalars`` mock returning each list in turn (open sessions, then unpublished ids)."""
    returned = []
    for items in results:
        result = MagicMock()
        result.all.return_value = items
        returned.append(result)
    return AsyncMock(side_effect=returned)


class TestCloseAnonymousVote:
    @pytest.mark.asyncio
    async def test_disables_the_select_posts_results_and_marks_them_published(self, bot):
        session = _close_db(loaded=_loaded_session(session_id=9))

        message = _make_poll_message()
        channel = MagicMock()
        channel.fetch_message = AsyncMock(return_value=message)
        bot.get_channel = MagicMock(return_value=channel)

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        view = message.edit.await_args.kwargs["view"]
        assert all(item.disabled for item in view.children)
        claim, mark = [call.args[0] for call in session.execute.await_args_list]
        assert "closed is false" in _compiled(claim)
        assert "published_at" in _compiled(mark)

    @pytest.mark.asyncio
    async def test_a_failed_fallback_send_is_logged_and_left_for_a_retry(self, bot):
        """close runs in a bare task, so an unhandled send failure would vanish silently."""
        session = _close_db(loaded=_loaded_session(session_id=9, message_id=None))

        channel = MagicMock()
        channel.send = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "no perms"))
        bot.get_channel = MagicMock(return_value=channel)

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        channel.send.assert_awaited_once()
        # Only the close claim ran; published_at stays NULL so startup retries.
        session.execute.assert_awaited_once()

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
        assert "published_at" in _compiled(session.execute.await_args.args[0])

    @pytest.mark.asyncio
    async def test_an_unresolvable_channel_is_left_for_a_retry(self, bot):
        session = _close_db(loaded=_loaded_session(session_id=9))

        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "nope"))

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        bot.fetch_channel.assert_awaited_once_with(555)
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_losing_concurrent_close_publishes_nothing(self, bot):
        """Second coroutine's UPDATE matches no row, so it must not post results twice."""
        session = _close_db(rowcount=0, loaded=_loaded_session(session_id=9))
        bot.get_channel = MagicMock()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        bot.get_channel.assert_not_called()
        session.scalar.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_publishes_nothing_when_the_row_vanishes_after_the_claim(self, bot):
        """Claimed the close, then the re-SELECT found nothing; must not crash the task."""
        session = _close_db(rowcount=1, loaded=None)
        bot.get_channel = MagicMock()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await close_anonymous_vote(bot, 9)

        bot.get_channel.assert_not_called()


class TestPublishVoteResults:
    @pytest.mark.asyncio
    async def test_does_nothing_when_results_are_already_out(self, bot):
        loaded = _loaded_session(session_id=9)
        loaded.published_at = 1800000000
        session = _close_db(loaded=loaded)
        bot.get_channel = MagicMock()

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await publish_vote_results(bot, 9)

        bot.get_channel.assert_not_called()
        session.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_a_session_that_is_already_being_published(self, bot):
        anonymous_vote._publishing.add(9)

        with patch("src.views.anonymous_vote.AsyncSessionLocal") as session_local:
            await publish_vote_results(bot, 9)

        session_local.assert_not_called()

    @pytest.mark.asyncio
    async def test_releases_the_guard_after_a_failure(self, bot):
        session = _close_db(loaded=_loaded_session(session_id=9))
        bot.get_channel = MagicMock(return_value=None)
        bot.fetch_channel = AsyncMock(side_effect=discord.HTTPException(MagicMock(), "nope"))

        with patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)):
            await publish_vote_results(bot, 9)

        assert 9 not in anonymous_vote._publishing


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

    @pytest.mark.asyncio
    async def test_a_reconnect_does_not_add_a_second_pending_close(self, bot):
        pending = MagicMock()
        pending.done.return_value = False
        bot.loop.create_task = MagicMock(return_value=pending)

        with (
            patch("src.views.anonymous_vote.schedule", new_callable=MagicMock),
            patch("src.views.anonymous_vote.close_anonymous_vote", new_callable=MagicMock),
        ):
            schedule_vote_close(bot, 7, 1800000000)
            schedule_vote_close(bot, 7, 1800000000)

        bot.loop.create_task.assert_called_once()
        assert anonymous_vote._close_tasks[7] is pending

    @pytest.mark.asyncio
    async def test_reschedules_once_the_previous_close_has_finished(self, bot):
        finished = MagicMock()
        finished.done.return_value = True
        anonymous_vote._close_tasks[7] = finished

        with (
            patch("src.views.anonymous_vote.schedule", new_callable=MagicMock),
            patch("src.views.anonymous_vote.close_anonymous_vote", new_callable=MagicMock),
        ):
            schedule_vote_close(bot, 7, 1800000000)

        bot.loop.create_task.assert_called_once()
        assert anonymous_vote._close_tasks[7] is not finished


class TestRegisterAnonymousVoteViews:
    @pytest.mark.asyncio
    async def test_schedules_close_for_future_session(self, bot):
        vote_session = _make_session(session_id=3, closes_at=1800000000)
        vote_session.candidates = [_make_candidate(session_id=3)]

        session = AsyncMock()
        session.scalars = _scalars([vote_session], [])

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

        session = AsyncMock()
        session.scalars = _scalars([vote_session], [])

        with (
            patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)),
            patch("src.views.anonymous_vote.schedule_vote_close") as mock_schedule_close,
            patch("src.views.anonymous_vote.close_anonymous_vote") as mock_close,
        ):
            await register_anonymous_vote_views(bot)

        mock_schedule_close.assert_not_called()
        mock_close.assert_called_once_with(bot, 4)

    @pytest.mark.asyncio
    async def test_retries_results_that_were_never_published(self, bot):
        session = AsyncMock()
        session.scalars = _scalars([], [11, 12])

        with (
            patch("src.views.anonymous_vote.AsyncSessionLocal", return_value=_session_ctx(session)),
            patch("src.views.anonymous_vote.publish_vote_results") as mock_publish,
        ):
            await register_anonymous_vote_views(bot)

        assert [c.args for c in mock_publish.call_args_list] == [(bot, 11), (bot, 12)]
        unpublished_query = _compiled(session.scalars.await_args_list[1].args[0])
        assert "closed is true" in unpublished_query
        assert "published_at is null" in unpublished_query


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

    def test_escapes_markdown_in_nominee_names(self):
        candidate = _make_candidate(candidate_id=1, name="[click](https://example.com)")

        embed = build_results_embed(_make_session(), [candidate], [])

        assert "\\[click](https://example.com)" in embed.description
