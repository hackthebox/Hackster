from unittest import mock
from unittest.mock import MagicMock, AsyncMock

import pytest
from discord import Forbidden, HTTPException

from src.helpers.ban import ban_member, _check_member, _dm_banned_member
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.database.models import Infraction, Ban
from src.helpers.ban import ban_member
from src.helpers.responses import SimpleResponse
from tests import helpers


class TestBanHelpers:

    @pytest.mark.asyncio
    async def test__check_member_staff_member(self, bot, guild, member):
        author = helpers.MockMember(name="Author User")
        member_is_staff = mock.Mock(return_value=True)
        with mock.patch('src.helpers.ban.member_is_staff', member_is_staff):
            response = await _check_member(bot, guild, member, author)
            assert isinstance(response, SimpleResponse)
            assert response.message == "You cannot ban another staff member."
            assert response.delete_after is None

    @pytest.mark.asyncio
    async def test__check_member_regular_member(self, bot, guild, member):
        author = helpers.MockMember(name="Author User")
        member_is_staff = mock.Mock(return_value=False)
        with mock.patch('src.helpers.ban.member_is_staff', member_is_staff):
            response = await _check_member(bot, guild, member, author)
            assert response is None

    @pytest.mark.asyncio
    async def test__check_member_user(self, bot, guild, user):
        author = helpers.MockMember(name="Author User")
        bot.get_member_or_user = AsyncMock()
        bot.get_member_or_user.return_value = user
        response = await _check_member(bot, guild, user, author)
        assert await bot.get_member_or_user.called_once_with(guild, user.id)
        assert response is None

    @pytest.mark.asyncio
    async def test__check_member_ban_bot(self, bot, guild, member):
        author = helpers.MockMember(name="Author User")
        member.bot = True
        response = await _check_member(bot, guild, member, author)
        assert isinstance(response, SimpleResponse)
        assert response.message == "You cannot ban a bot."
        assert response.delete_after is None

    @pytest.mark.asyncio
    async def test__check_member_ban_self(self, bot, guild, member):
        author = member
        response = await _check_member(bot, guild, member, author)
        assert isinstance(response, SimpleResponse)
        assert response.message == "You cannot ban yourself."
        assert response.delete_after is None

    @pytest.mark.asyncio
    async def test__dm_banned_member_success(self, guild, member):
        member.send = AsyncMock()
        end_date = "2023-05-19"
        reason = "Violation of community guidelines"
        result = await _dm_banned_member(end_date, guild, member, reason)
        member.send.assert_awaited_once_with(
            f"You have been banned from {guild.name} until {end_date} (UTC). "
            f"To appeal the ban, please reach out to an Administrator.\n"
            f"Following is the reason given:\n>>> {reason}\n"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test__dm_banned_member_forbidden_exception(self, guild, member):
        class MockResponse:
            def __init__(self, status, reason):
                self.status = status
                self.reason = reason

        response = MockResponse(403, "Forbidden")
        message = {
            "code": 403,
            "message": "Forbidden",
        }

        forbidden = Forbidden(response, message)
        member.send = AsyncMock(side_effect=forbidden)
        with pytest.warns(None):
            result = await _dm_banned_member("2023-05-19", guild, member, "Violation of community guidelines")
        assert result is False

    @pytest.mark.asyncio
    async def test__dm_banned_member_http_exception(self, guild, member):
        class MockResponse:
            def __init__(self, status, reason):
                self.status = status
                self.reason = reason

        response = MockResponse(500, "Internal Server Error")
        message = {
            "code": 500,
            "message": "Internal Server Error",
        }

        http_exception = HTTPException(response, message)
        member.send = AsyncMock(side_effect=http_exception)
        with pytest.warns(None):
            result = await _dm_banned_member("2023-05-19", guild, member, "Violation of community guidelines")
        assert result is False


class TestBanMember:

    @pytest.mark.asyncio
    async def test_ban_member_valid_duration(self, bot, guild, member, author):
        duration = "1d"
        reason = "xf reason"
        member.display_name = "Banned Member"

        with (
            mock.patch("src.helpers.ban._check_member", return_value=None),
            mock.patch("src.helpers.ban._dm_banned_member", return_value=True),
            mock.patch("src.helpers.ban._get_ban_or_create", return_value=(1, False)),
            mock.patch("src.helpers.ban.validate_duration", return_value=(1684276900, "")),
        ):
            mock_channel = helpers.MockTextChannel()
            mock_channel.send.return_value = MagicMock()
            guild.get_channel.return_value = mock_channel

            result = await ban_member(bot, guild, member, duration, reason)
            assert isinstance(result, SimpleResponse)
            assert result.message == f"{member.display_name} ({member.id}) has been banned until 2023-05-16 22:41:40 " \
                                     f"(UTC)."

    @pytest.mark.asyncio
    async def test_ban_member_success(self, ctx, bot, guild):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        user = helpers.MockMember(id=2, name="Banned User")
        mock_ban = MagicMock()
        mock_infraction = MagicMock()
        mock_session = AsyncMock()

        reason = 'Why not?'
        duration = '1h'

        # Patching the necessary classes and functions
        with patch('src.helpers.ban.Ban', return_value=mock_ban):
            with patch('src.helpers.ban.Infraction', return_value=mock_infraction):
                with patch('src.helpers.ban.AsyncSessionLocal', return_value=mock_session):
                    # Creating an instance of the Ban class
                    ban_instance = Ban(
                        user_id=user.id, reason=reason, moderator_id=ctx.user.id,
                        unban_time=datetime.now() + timedelta(hours=1), approved=False
                    )

                    # Creating an instance of the Infraction class
                    infraction_instance = Infraction(
                        user_id=user.id, reason=f"Previously banned for: {reason}", weight=0, moderator_id=ctx.user.id,
                        date=datetime.now().date()
                    )

                    # Mocking the session.add() and session.commit() methods
                    mock_session.add.side_effect = lambda \
                            obj: mock_session if obj == ban_instance or obj == infraction_instance else None
                    mock_session.commit.return_value = None

                    response = await ban_member(bot, guild, user, duration, reason, ctx.user, False)
                    assert isinstance(response, SimpleResponse)
                    assert response.message == f"Member {user.display_name} has been banned permanently."

    @pytest.mark.asyncio
    async def test_ban_member_no_reason_success(self, ctx, bot, guild):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        user = helpers.MockMember(id=2, name="Banned User")
        mock_ban = MagicMock()
        mock_infraction = MagicMock()
        mock_session = AsyncMock()

        reason = ''
        duration = '1h'

        # Patching the necessary classes and functions
        with patch('src.helpers.ban.Ban', return_value=mock_ban):
            with patch('src.helpers.ban.Infraction', return_value=mock_infraction):
                with patch('src.helpers.ban.AsyncSessionLocal', return_value=mock_session):
                    # Creating an instance of the Ban class
                    ban_instance = Ban(
                        user_id=user.id, reason=reason, moderator_id=ctx.user.id,
                        unban_time=datetime.now() + timedelta(hours=1), approved=False
                    )

                    # Creating an instance of the Infraction class
                    infraction_instance = Infraction(
                        user_id=user.id, reason=f"Previously banned for: {reason}", weight=0, moderator_id=ctx.user.id,
                        date=datetime.now().date()
                    )

                    # Mocking the session.add() and session.commit() methods
                    mock_session.add.side_effect = lambda \
                            obj: mock_session if obj == ban_instance or obj == infraction_instance else None
                    mock_session.commit.return_value = None

                    response = await ban_member(bot, guild, user, duration, reason, ctx.user, False)
                    assert isinstance(response, SimpleResponse)
                    assert response.message == f"Member {user.display_name} has been banned permanently."

    @pytest.mark.asyncio
    async def test_ban_member_no_author_success(self, ctx, bot, guild):
        # bot.id = 1337
        user = helpers.MockMember(id=2, name="Banned User")
        mock_ban = MagicMock()
        mock_infraction = MagicMock()
        mock_session = AsyncMock()

        reason = ''
        duration = '1h'

        # Patching the necessary classes and functions
        with patch('src.helpers.ban.Ban', return_value=mock_ban):
            with patch('src.helpers.ban.Infraction', return_value=mock_infraction):
                with patch('src.helpers.ban.AsyncSessionLocal', return_value=mock_session):
                    # Creating an instance of the Ban class
                    ban_instance = Ban(
                        user_id=user.id, reason=reason, moderator_id=1337,
                        unban_time=datetime.now() + timedelta(hours=1), approved=False
                    )

                    # Creating an instance of the Infraction class
                    infraction_instance = Infraction(
                        user_id=user.id, reason=f"Previously banned for: {reason}", weight=0, moderator_id=1337,
                        date=datetime.now().date()
                    )

                    # Mocking the session.add() and session.commit() methods
                    mock_session.add.side_effect = lambda \
                            obj: mock_session if obj == ban_instance or obj == infraction_instance else None
                    mock_session.commit.return_value = None

                    response = await ban_member(bot, guild, user, duration, reason, None, False)
                    assert isinstance(response, SimpleResponse)
                    assert response.message == f"Member {user.display_name} has been banned permanently."

    @pytest.mark.asyncio
    async def test_ban_member_staff(self, ctx, bot, guild):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        user = helpers.MockMember(id=2, name="Banned User")
        with patch('src.helpers.ban.member_is_staff', return_value=True):
            response = await ban_member(
                bot, guild, user, "1d", "spamming", author=ctx.user, needs_approval=True
            )

        assert isinstance(response, SimpleResponse)
        assert response.message == "You cannot ban another staff member."

    @pytest.mark.asyncio
    async def test_ban_member_bot(self, ctx, bot, guild):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        member = helpers.MockMember(id=2, name="Bot Member", bot=True)
        with patch('src.helpers.ban.member_is_staff', return_value=False):
            response = await ban_member(
                bot, guild, member, "1d", "spamming", author=ctx.user, needs_approval=True
            )

        assert isinstance(response, SimpleResponse)
        assert response.message == "You cannot ban a bot."

    @pytest.mark.asyncio
    async def test_ban_self(self, ctx, bot, guild):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        with patch('src.helpers.ban.member_is_staff', return_value=False):
            response = await ban_member(
                bot, guild, ctx.user, "1d", "spamming", author=ctx.user, needs_approval=True
            )

        assert isinstance(response, SimpleResponse)
        assert response.message == "You cannot ban yourself."
