from datetime import datetime, timedelta
from unittest import mock

import pytest
from sqlalchemy.exc import NoResultFound

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
    async def test_mute_keeps_a_reference_to_the_unmute_task(self, bot, ctx):
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

        assert len(cog._pending_tasks) == 1
        member.timeout.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unmute_when_due_removes_the_mute(self, bot):
        cog = MuteCog(bot)
        member = helpers.MockMember()
        guild = helpers.MockGuild()
        run_at = datetime.now() - timedelta(seconds=1)

        with mock.patch("src.cmds.core.mute.unmute_member", new_callable=mock.AsyncMock) as unmute:
            await cog._unmute_when_due(guild, member, run_at)

        unmute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unmute_when_due_ignores_a_cleared_record(self, bot):
        cog = MuteCog(bot)
        run_at = datetime.now() - timedelta(seconds=1)

        with mock.patch("src.cmds.core.mute.unmute_member", side_effect=NoResultFound("already removed")):
            await cog._unmute_when_due(helpers.MockGuild(), helpers.MockMember(), run_at)

    @pytest.mark.asyncio
    async def test_unmute_when_due_logs_unexpected_failures(self, bot):
        cog = MuteCog(bot)
        run_at = datetime.now() - timedelta(seconds=1)

        async def explode(*args, **kwargs):
            raise RuntimeError("discord unavailable")

        with mock.patch("src.cmds.core.mute.unmute_member", side_effect=explode):
            await cog._unmute_when_due(helpers.MockGuild(), helpers.MockMember(), run_at)
