from unittest.mock import patch

import pytest

from src.helpers.ban import ban_member
from src.helpers.responses import SimpleResponse
from tests import helpers


class TestBanMember:

    @pytest.mark.asyncio
    async def test_ban_member_success(self, ctx, bot, guild):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        user = helpers.MockMember(id=2, name="Banned User")
        result = await ban_member(bot, guild, user, '1h', 'Why not?', ctx.user, False)
        assert isinstance(result, SimpleResponse)

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
