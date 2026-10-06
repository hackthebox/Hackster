import asyncio
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest import mock

import pytest
from sqlalchemy.exc import NoResultFound
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

    @pytest.mark.asyncio
    async def test_due_ban_is_scheduled(self, bot):
        guild = helpers.MockGuild()
        member = helpers.MockMember()
        bot.get_guild.return_value = guild
        bot.get_member_or_user = mock.AsyncMock(return_value=member)
        ban = SimpleNamespace(user_id=member.id, unban_time=int(datetime.now().timestamp()) - 15)
        session = _Session([ban], "unban_time")
        cog = _cog(bot)

        with mock.patch.object(scheduled_tasks.settings, "guild_ids", [guild.id]), mock.patch.object(
            scheduled_tasks, "AsyncSessionLocal", return_value=session
        ), mock.patch.object(scheduled_tasks, "unban_member", new_callable=mock.AsyncMock) as unban:
            await cog.auto_unban()
            await asyncio.wait_for(asyncio.gather(*cog._pending_tasks), timeout=1)

        unban.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_missing_guild_member_and_bad_timestamp_are_skipped(self, bot):
        guild = helpers.MockGuild()
        bot.get_guild.side_effect = lambda guild_id: guild if guild_id == guild.id else None
        bot.get_member_or_user = mock.AsyncMock(return_value=None)
        now = int(datetime.now().timestamp())
        mute = SimpleNamespace(user_id=1, unmute_time=now - 5)
        bad_mute = SimpleNamespace(user_id=2, unmute_time=10**18)
        ban = SimpleNamespace(user_id=3, unban_time=now - 5)
        bad_ban = SimpleNamespace(user_id=4, unban_time=10**18)
        cog = _cog(bot)

        def session_for(rows):
            session = mock.Mock()
            session.__aenter__ = mock.AsyncMock(return_value=session)
            session.__aexit__ = mock.AsyncMock(return_value=False)
            result = mock.Mock()
            result.all.return_value = rows
            session.scalars = mock.AsyncMock(return_value=result)
            return session

        with mock.patch.object(scheduled_tasks.settings, "guild_ids", [guild.id + 1, guild.id]), mock.patch.object(
            scheduled_tasks, "AsyncSessionLocal", side_effect=[session_for([ban, bad_ban]), session_for([mute, bad_mute])]
        ), mock.patch.object(scheduled_tasks, "unban_member", new_callable=mock.AsyncMock) as unban, mock.patch.object(
            scheduled_tasks, "unmute_member", new_callable=mock.AsyncMock
        ) as unmute:
            await cog.auto_unban()
            await cog.auto_unmute()
            await asyncio.wait_for(asyncio.gather(*cog._pending_tasks), timeout=1)

        unban.assert_awaited_once()
        assert unban.await_args.args[1].id == ban.user_id
        unmute.assert_awaited_once()
        assert unmute.await_args.args[1].id == mute.user_id

    @pytest.mark.asyncio
    async def test_all_tasks_schedules_both_and_survives_errors(self, bot):
        cog = _cog(bot)
        cog.auto_unban = mock.AsyncMock()
        cog.auto_unmute = mock.AsyncMock()
        await cog.all_tasks()
        cog.auto_unban.assert_awaited_once()
        cog.auto_unmute.assert_awaited_once()

        cog.auto_unban.side_effect = RuntimeError("database unavailable")
        await cog.all_tasks()
        cog.auto_unmute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_scheduled_swallows_cleared_records_and_failures(self, bot):
        cog = _cog(bot)
        run_at = datetime.now() - timedelta(seconds=1)

        async def already_cleared():
            raise NoResultFound("mute already removed")

        async def failed():
            raise RuntimeError("discord unavailable")

        await cog._run_scheduled(already_cleared(), run_at, "unmute")
        await cog._run_scheduled(failed(), run_at, "unban")
