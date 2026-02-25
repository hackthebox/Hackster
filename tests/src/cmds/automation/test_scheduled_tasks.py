"""Tests for ScheduledTasks cog (parental consent: auto_remove_minor_role, on_member_join)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cmds.automation import scheduled_tasks
from src.database.models import MinorReport
from src.helpers.minor_verification import APPROVED, CONSENT_VERIFIED
from tests import helpers


@pytest.fixture(autouse=True)
def stop_task_loop():
    """Prevent ScheduledTasks from starting the background task loop in tests."""

    def init_no_loop(self, bot):
        self.bot = bot
        # Do not call self.all_tasks.start()

    with patch.object(scheduled_tasks.ScheduledTasks, "__init__", init_no_loop):
        yield


class TestScheduledTasksMinorRole:
    """Tests for minor-role-related scheduled task logic."""

    @pytest.mark.asyncio
    async def test_auto_remove_minor_role_no_reports(self, bot):
        """Test auto_remove_minor_role when there are no reports."""
        mock_session = MagicMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = []
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with (
            patch('src.cmds.automation.scheduled_tasks.AsyncSessionLocal', return_value=AsyncContextManager()),
            patch('src.cmds.automation.scheduled_tasks.settings') as mock_settings,
        ):
            mock_settings.guild_ids = [123]
            cog = scheduled_tasks.ScheduledTasks(bot)
            await cog.auto_remove_minor_role()
            # No role removals when there are no reports

    @pytest.mark.asyncio
    async def test_auto_remove_minor_role_skips_when_not_yet_18(self, bot):
        """Test auto_remove_minor_role skips reports where user has not reached 18."""
        now = datetime.now(timezone.utc)
        # Report from 1 year ago, suspected_age 17 -> expires in 1 year from creation
        created = now - timedelta(days=365)
        report = MinorReport(
            id=1,
            user_id=999,
            reporter_id=2,
            suspected_age=17,
            evidence="x",
            report_message_id=1,
            status=CONSENT_VERIFIED,
            created_at=created,
            updated_at=now,
        )
        mock_session = MagicMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = [report]
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with (
            patch('src.cmds.automation.scheduled_tasks.AsyncSessionLocal', return_value=AsyncContextManager()),
            patch('src.cmds.automation.scheduled_tasks.settings') as mock_settings,
        ):
            mock_settings.guild_ids = [123]
            bot.get_guild = MagicMock(return_value=helpers.MockGuild())
            mock_member = helpers.MockMember(id=999, name="User")
            mock_member.remove_roles = AsyncMock()
            role = helpers.MockRole(id=456, name="Verified Minor")
            mock_member.roles = [role]
            bot.get_member_or_user = AsyncMock(return_value=mock_member)
            bot.get_guild.return_value.get_role = lambda rid: role if rid == 456 else None

            cog = scheduled_tasks.ScheduledTasks(bot)
            await cog.auto_remove_minor_role()

            # User is 17, report created 1 year ago -> 1 year until 18 -> not yet expired
            mock_member.remove_roles.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_remove_minor_role_removes_when_18(self, bot):
        """Test auto_remove_minor_role removes role when user has reached 18."""
        now = datetime.now(timezone.utc)
        # Report from 3 years ago, suspected_age 15 -> 3 years until 18 -> expired
        created = now - timedelta(days=365 * 3)
        report = MinorReport(
            id=1,
            user_id=999,
            reporter_id=2,
            suspected_age=15,
            evidence="x",
            report_message_id=1,
            status=CONSENT_VERIFIED,
            created_at=created,
            updated_at=now,
        )
        mock_session = MagicMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = [report]
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with (
            patch('src.cmds.automation.scheduled_tasks.AsyncSessionLocal', return_value=AsyncContextManager()),
            patch('src.cmds.automation.scheduled_tasks.settings') as mock_settings,
        ):
            mock_settings.guild_ids = [123]
            mock_settings.roles.VERIFIED_MINOR = 456
            guild = helpers.MockGuild()
            role = helpers.MockRole(id=456, name="Verified Minor")
            guild.get_role = lambda rid: role if rid == 456 else None
            bot.get_guild = MagicMock(return_value=guild)
            mock_member = helpers.MockMember(id=999, name="User")
            mock_member.roles = [role]
            mock_member.remove_roles = AsyncMock()
            bot.get_member_or_user = AsyncMock(return_value=mock_member)

            cog = scheduled_tasks.ScheduledTasks(bot)
            await cog.auto_remove_minor_role()

            mock_member.remove_roles.assert_called_once_with(role, atomic=True)

    @pytest.mark.asyncio
    async def test_on_member_join_no_report(self, bot):
        """Test on_member_join does nothing when no consent_verified report for user."""
        member = helpers.MockMember(id=999, name="User")
        member.guild = helpers.MockGuild()

        mock_session = MagicMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = None
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with (
            patch('src.cmds.automation.scheduled_tasks.AsyncSessionLocal', return_value=AsyncContextManager()),
            patch('src.cmds.automation.scheduled_tasks.assign_minor_role', new_callable=AsyncMock) as assign_mock,
        ):
            cog = scheduled_tasks.ScheduledTasks(bot)
            await cog.on_member_join(member)

            assign_mock.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_member_join_assigns_when_under_18(self, bot):
        """Test on_member_join assigns minor role when report is consent_verified and user under 18."""
        member = helpers.MockMember(id=999, name="User")
        member.guild = helpers.MockGuild()
        now = datetime.now(timezone.utc)
        created = now - timedelta(days=100)
        report = MinorReport(
            id=1,
            user_id=999,
            reporter_id=2,
            suspected_age=15,
            evidence="x",
            report_message_id=1,
            status=CONSENT_VERIFIED,
            created_at=created,
            updated_at=now,
        )

        mock_session = MagicMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = report
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with (
            patch('src.cmds.automation.scheduled_tasks.AsyncSessionLocal', return_value=AsyncContextManager()),
            patch('src.cmds.automation.scheduled_tasks.assign_minor_role', new_callable=AsyncMock) as assign_mock,
        ):
            cog = scheduled_tasks.ScheduledTasks(bot)
            await cog.on_member_join(member)

            assign_mock.assert_called_once_with(member, member.guild)

    @pytest.mark.asyncio
    async def test_on_member_join_skips_when_already_18(self, bot):
        """Test on_member_join does not assign when user has reached 18 (expires_at in past)."""
        member = helpers.MockMember(id=999, name="User")
        member.guild = helpers.MockGuild()
        now = datetime.now(timezone.utc)
        # Report from 5 years ago, suspected_age 15 -> would be 20 now
        created = now - timedelta(days=365 * 5)
        report = MinorReport(
            id=1,
            user_id=999,
            reporter_id=2,
            suspected_age=15,
            evidence="x",
            report_message_id=1,
            status=CONSENT_VERIFIED,
            created_at=created,
            updated_at=now,
        )

        mock_session = MagicMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = report
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with (
            patch('src.cmds.automation.scheduled_tasks.AsyncSessionLocal', return_value=AsyncContextManager()),
            patch('src.cmds.automation.scheduled_tasks.assign_minor_role', new_callable=AsyncMock) as assign_mock,
        ):
            cog = scheduled_tasks.ScheduledTasks(bot)
            await cog.on_member_join(member)

            assign_mock.assert_not_called()
