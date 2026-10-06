from datetime import datetime
from unittest import mock

import pytest

from src.cmds.core import mute
from src.cmds.core.mute import MuteCog
from tests import helpers


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def add(self, obj):
        self.obj = obj

    async def commit(self):
        return None


class TestMuteCog:
    """Test the `Mute` cog."""

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        mute.setup(bot)

        bot.add_cog.assert_called_once()

    @pytest.mark.asyncio
    async def test_mute_applies_timeout_without_its_own_unmute_task(self, bot, ctx):
        member = helpers.MockMember(bot=False)
        member.timeout = mock.AsyncMock()
        member.send = mock.AsyncMock()
        ctx.user = helpers.MockMember()
        bot.get_member_or_user = mock.AsyncMock(return_value=member)
        cog = MuteCog(bot)
        unmute_at = int(datetime.now().timestamp()) + 60

        with mock.patch("src.cmds.core.mute.member_is_staff", return_value=False), mock.patch(
            "src.cmds.core.mute.validate_duration", return_value=(unmute_at, "")
        ), mock.patch("src.cmds.core.mute.AsyncSessionLocal", return_value=_Session()):
            await cog.mute.callback(cog, ctx, member, "1m", "testing")

        member.timeout.assert_awaited_once()
