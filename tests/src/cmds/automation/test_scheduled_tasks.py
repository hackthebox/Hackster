import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

import pytest
from sqlalchemy.sql.elements import BindParameter

from src.cmds.automation import scheduled_tasks
from tests import helpers


def _bound_values(stmt):
    values = []
    for bind in stmt.compile().binds.values():
        if isinstance(bind, BindParameter) and isinstance(bind.value, (int, float)):
            values.append(bind.value)
    return values


class _Session:
    def __init__(self, rows, column):
        self.rows = rows
        self.column = column
        self.stmt = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def scalars(self, stmt):
        self.stmt = stmt
        cutoffs = [value for value in _bound_values(stmt) if value > 10**8]
        cutoff = cutoffs[-1] if cutoffs else 0
        matched = [row for row in self.rows if getattr(row, self.column) <= cutoff]
        result = mock.Mock()
        result.all.return_value = matched
        return result


def _cog(bot):
    with mock.patch("discord.ext.tasks.Loop.start"):
        return scheduled_tasks.ScheduledTasks(bot)


class TestScheduledTasks:
    """Unmutes must be scheduled in seconds and must not wait on long bans."""

    def test_due_before_epoch_is_unix_seconds(self):
        now = datetime.now().timestamp()
        due_before = scheduled_tasks.ScheduledTasks._due_before_epoch()

        assert now < due_before < now + 90
        assert due_before < 10**11

    @pytest.mark.asyncio
    async def test_far_future_ban_does_not_block_scheduling(self, bot):
        """A multi-year ban must not stall the loop that also unmutes members."""
        guild = helpers.MockGuild()
        member = helpers.MockMember()
        bot.get_guild.return_value = guild
        bot.get_member_or_user = mock.AsyncMock(return_value=member)
        far_future = int((datetime.now() + timedelta(weeks=500)).timestamp())
        ban = SimpleNamespace(user_id=member.id, unban_time=far_future)
        session = _Session([ban], "unban_time")
        cog = _cog(bot)

        with mock.patch.object(scheduled_tasks.settings, "guild_ids", [guild.id]), mock.patch.object(
            scheduled_tasks, "AsyncSessionLocal", return_value=session
        ):
            await asyncio.wait_for(cog.auto_unban(), timeout=1)

        assert cog._pending_tasks == set()

    @pytest.mark.asyncio
    async def test_expired_mute_is_cleared_without_waiting_on_future_mutes(self, bot):
        guild = helpers.MockGuild()
        member = helpers.MockMember()
        bot.get_guild.return_value = guild
        bot.get_member_or_user = mock.AsyncMock(return_value=member)
        now = int(datetime.now().timestamp())
        expired = SimpleNamespace(user_id=member.id, unmute_time=now - 30)
        still_muted = SimpleNamespace(user_id=member.id + 1, unmute_time=now + 7200)
        session = _Session([expired, still_muted], "unmute_time")
        cog = _cog(bot)

        with mock.patch.object(scheduled_tasks.settings, "guild_ids", [guild.id]), mock.patch.object(
            scheduled_tasks, "AsyncSessionLocal", return_value=session
        ), mock.patch.object(scheduled_tasks, "unmute_member", new_callable=mock.AsyncMock) as unmute:
            await asyncio.wait_for(cog.auto_unmute(), timeout=1)
            pending = list(cog._pending_tasks)
            if pending:
                await asyncio.wait_for(asyncio.gather(*pending), timeout=1)

        unmute.assert_awaited_once()
        assert session.stmt is not None
        cutoff = max(value for value in _bound_values(session.stmt) if value > 10**8)
        assert now < cutoff < now + 90
