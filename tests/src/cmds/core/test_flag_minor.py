from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cmds.core import flag_minor
from src.database.models import MinorReport
from tests import helpers


class TestFlagMinorCog:
    """Test the `FlagMinor` cog."""

    @pytest.mark.asyncio
    async def test_flag_minor_success_no_consent(self, ctx, bot):
        """Test flagging a minor where Nexus reports no parental consent — report created."""
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")

        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")

        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]

        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        bot.get_member_or_user.return_value = user

        with (
            patch("src.cmds.core.flag_minor.get_htb_user_id_for_discord", new_callable=AsyncMock) as get_link_mock,
            patch("src.cmds.core.flag_minor.check_parental_consent", new_callable=AsyncMock) as consent_mock,
            patch("src.cmds.core.flag_minor.get_active_minor_report", new_callable=AsyncMock) as get_report_mock,
            patch("src.cmds.core.flag_minor.AsyncSessionLocal") as session_mock,
            patch("src.cmds.core.flag_minor.settings") as mock_settings,
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = 999

            get_link_mock.return_value = None
            consent_mock.return_value = False
            get_report_mock.return_value = None

            mock_session = AsyncMock()
            session_mock.return_value.__aenter__.return_value = mock_session

            mock_message = helpers.MockMessage(id=12345)
            mock_channel = MagicMock()
            mock_channel.send = AsyncMock(return_value=mock_message)
            mock_channel.fetch_message = AsyncMock(return_value=mock_message)
            ctx.guild.get_channel = MagicMock(return_value=mock_channel)

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(cog, ctx, user, 15, "User stated they are 15 in chat")

            assert ctx.respond.called
            consent_mock.assert_called_once_with(user.id)

    @pytest.mark.asyncio
    async def test_flag_minor_consent_already_exists(self, ctx, bot):
        """Test flagging a minor when Nexus confirms parental consent already on file."""
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")

        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")

        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]

        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        bot.get_member_or_user.return_value = user

        with (
            patch("src.cmds.core.flag_minor.check_parental_consent", new_callable=AsyncMock) as consent_mock,
            patch("src.cmds.core.flag_minor.get_active_minor_report", new_callable=AsyncMock) as get_report_mock,
            patch("src.cmds.core.flag_minor.assign_minor_role", new_callable=AsyncMock) as assign_role_mock,
            patch("src.cmds.core.flag_minor.settings") as mock_settings,
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = 999

            get_report_mock.return_value = None
            consent_mock.return_value = True
            assign_role_mock.return_value = True

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(cog, ctx, user, 15, "User stated they are 15 in chat")

            assert ctx.respond.called
            consent_mock.assert_called_once_with(user.id)

    @pytest.mark.asyncio
    async def test_flag_minor_existing_report(self, ctx, bot):
        """Test flagging a minor when an active report already exists — report updated."""
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")

        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")

        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]

        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        bot.get_member_or_user.return_value = user

        existing_report = MinorReport(
            id=1,
            user_id=2,
            reporter_id=3,
            suspected_age=15,
            evidence="Previous evidence",
            report_message_id=99999,
            status="pending",
        )

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=existing_report)
        mock_session.commit = AsyncMock()

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        mock_message = helpers.MockMessage(id=99999)
        mock_channel = MagicMock()
        mock_channel.fetch_message = AsyncMock(return_value=mock_message)
        ctx.guild.get_channel = MagicMock(return_value=mock_channel)

        with (
            patch("src.cmds.core.flag_minor.get_htb_user_id_for_discord", new_callable=AsyncMock) as get_link_mock,
            patch("src.cmds.core.flag_minor.check_parental_consent", new_callable=AsyncMock) as consent_mock,
            patch("src.cmds.core.flag_minor.get_active_minor_report", new_callable=AsyncMock) as get_report_mock,
            patch("src.cmds.core.flag_minor.AsyncSessionLocal", return_value=AsyncContextManager()),
            patch("src.cmds.core.flag_minor.settings") as mock_settings,
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = 999

            get_link_mock.return_value = None
            consent_mock.return_value = False
            get_report_mock.return_value = existing_report

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(cog, ctx, user, 15, "User stated they are 15 in chat")

            assert ctx.respond.called

    @pytest.mark.asyncio
    async def test_flag_minor_invalid_age(self, ctx, bot):
        """Test flagging with an invalid age (outside 1-17 range)."""
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        user = helpers.MockMember(id=2, name="User")
        bot.get_member_or_user.return_value = user

        cog = flag_minor.FlagMinorCog(bot)

        await cog.flag_minor.callback(cog, ctx, user, 0, "Evidence")
        assert ctx.respond.called or ctx.followup.send.called

        ctx.reset_mock()
        await cog.flag_minor.callback(cog, ctx, user, 18, "Evidence")
        assert ctx.respond.called or ctx.followup.send.called

    @pytest.mark.asyncio
    async def test_flag_minor_no_review_channel_configured(self, ctx, bot):
        """Test early return when MINOR_REVIEW channel is not configured."""
        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")
        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]
        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        bot.get_member_or_user.return_value = user

        with (
            patch("src.cmds.core.flag_minor.get_htb_user_id_for_discord", new_callable=AsyncMock),
            patch("src.cmds.core.flag_minor.check_parental_consent", new_callable=AsyncMock) as consent_mock,
            patch("src.cmds.core.flag_minor.get_active_minor_report", new_callable=AsyncMock),
            patch("src.cmds.core.flag_minor.settings") as mock_settings,
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = None
            consent_mock.return_value = False

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(cog, ctx, user, 15, "Evidence")

            ctx.edit.assert_called_once()
            assert "not configured" in ctx.edit.call_args[1].get("content", "").lower()

    @pytest.mark.asyncio
    async def test_flag_minor_review_channel_not_found(self, ctx, bot):
        """Test early return when review channel ID is set but channel not found."""
        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")
        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]
        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        ctx.guild.get_channel = MagicMock(return_value=None)
        bot.get_member_or_user.return_value = user

        with (
            patch("src.cmds.core.flag_minor.get_htb_user_id_for_discord", new_callable=AsyncMock),
            patch("src.cmds.core.flag_minor.check_parental_consent", new_callable=AsyncMock) as consent_mock,
            patch("src.cmds.core.flag_minor.get_active_minor_report", new_callable=AsyncMock),
            patch("src.cmds.core.flag_minor.settings") as mock_settings,
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = 999
            consent_mock.return_value = False

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(cog, ctx, user, 15, "Evidence")

            ctx.edit.assert_called_once()
            assert "not found" in ctx.edit.call_args[1].get("content", "").lower()

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        flag_minor.setup(bot)
        bot.add_cog.assert_called_once()
