from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.database.models import Infraction, Ban
from src.helpers.ban import ban_member
from src.helpers.responses import SimpleResponse
from tests import helpers


class TestBanMember:

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
