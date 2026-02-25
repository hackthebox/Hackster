from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cmds.core import flag_minor
from src.database.models import MinorReport, MinorReviewReviewer
from tests import helpers


class TestFlagMinorCog:
    """Test the `FlagMinor` cog."""

    @pytest.mark.asyncio
    async def test_flag_minor_success_no_htb_account(self, ctx, bot):
        """Test flagging a minor with no HTB account linked."""
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        
        # Create verified role mock
        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")
        
        # Mock user with verified role
        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]  # User has verified role
        
        # Mock guild get_role
        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        
        bot.get_member_or_user.return_value = user

        with (
            patch('src.cmds.core.flag_minor.get_htb_user_id_for_discord', new_callable=AsyncMock) as get_link_mock,
            patch('src.cmds.core.flag_minor.get_account_identifier_for_discord', new_callable=AsyncMock) as get_acct_mock,
            patch('src.cmds.core.flag_minor.check_parental_consent', new_callable=AsyncMock) as consent_mock,
            patch('src.cmds.core.flag_minor.get_active_minor_report', new_callable=AsyncMock) as get_report_mock,
            patch('src.cmds.core.flag_minor.AsyncSessionLocal') as session_mock,
            patch('src.cmds.core.flag_minor.settings') as mock_settings
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = 999

            # Mock no HTB account linked
            get_link_mock.return_value = None
            get_acct_mock.return_value = None
            get_report_mock.return_value = None  # No existing report

            # Mock session for database operations
            mock_session = AsyncMock()
            session_mock.return_value.__aenter__.return_value = mock_session

            # Mock review channel (command uses ctx.guild.get_channel)
            mock_message = helpers.MockMessage(id=12345)
            mock_channel = MagicMock()
            mock_channel.send = AsyncMock(return_value=mock_message)
            mock_channel.fetch_message = AsyncMock(return_value=mock_message)
            ctx.guild.get_channel = MagicMock(return_value=mock_channel)

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(
                cog, ctx, user, 15, "User stated they are 15 in chat"
            )

            # Assertions
            assert ctx.respond.called

    @pytest.mark.asyncio
    async def test_flag_minor_success_htb_account_no_consent(self, ctx, bot):
        """Test flagging a minor with HTB account but no parental consent."""
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        
        # Create verified role mock
        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")
        
        # Mock user with verified role
        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]
        
        # Mock guild get_role
        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        
        bot.get_member_or_user.return_value = user

        with (
            patch('src.cmds.core.flag_minor.get_htb_user_id_for_discord', new_callable=AsyncMock) as get_link_mock,
            patch('src.cmds.core.flag_minor.get_account_identifier_for_discord', new_callable=AsyncMock) as get_acct_mock,
            patch('src.cmds.core.flag_minor.check_parental_consent', new_callable=AsyncMock) as consent_mock,
            patch('src.cmds.core.flag_minor.get_active_minor_report', new_callable=AsyncMock) as get_report_mock,
            patch('src.cmds.core.flag_minor.AsyncSessionLocal') as session_mock,
            patch('src.cmds.core.flag_minor.settings') as mock_settings
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = 999

            get_link_mock.return_value = 123
            get_acct_mock.return_value = "test-account-uuid"
            get_report_mock.return_value = None
            consent_mock.return_value = False

            mock_session = AsyncMock()
            session_mock.return_value.__aenter__.return_value = mock_session

            mock_message = helpers.MockMessage(id=12345)
            mock_channel = MagicMock()
            mock_channel.send = AsyncMock(return_value=mock_message)
            mock_channel.fetch_message = AsyncMock(return_value=mock_message)
            ctx.guild.get_channel = MagicMock(return_value=mock_channel)

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(
                cog, ctx, user, 15, "User stated they are 15 in chat"
            )

            assert ctx.respond.called

    @pytest.mark.asyncio
    async def test_flag_minor_consent_already_exists(self, ctx, bot):
        """Test flagging a minor when parental consent already exists."""
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        
        # Create verified role mock
        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")
        
        # Mock user with verified role
        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]
        
        # Mock guild get_role
        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        
        bot.get_member_or_user.return_value = user

        with (
            patch('src.cmds.core.flag_minor.get_htb_user_id_for_discord', new_callable=AsyncMock) as get_link_mock,
            patch('src.cmds.core.flag_minor.get_account_identifier_for_discord', new_callable=AsyncMock) as get_acct_mock,
            patch('src.cmds.core.flag_minor.check_parental_consent', new_callable=AsyncMock) as consent_mock,
            patch('src.cmds.core.flag_minor.get_active_minor_report', new_callable=AsyncMock) as get_report_mock,
            patch('src.cmds.core.flag_minor.assign_minor_role', new_callable=AsyncMock) as assign_role_mock,
            patch('src.cmds.core.flag_minor.settings') as mock_settings
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = 999

            get_link_mock.return_value = 123
            get_acct_mock.return_value = "test-account-uuid"
            get_report_mock.return_value = None
            consent_mock.return_value = True
            assign_role_mock.return_value = True

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(
                cog, ctx, user, 15, "User stated they are 15 in chat"
            )

            assert ctx.respond.called

    @pytest.mark.asyncio
    async def test_flag_minor_existing_report(self, ctx, bot):
        """Test flagging a minor when a report already exists."""
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        
        # Create verified role mock
        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")
        
        # Mock user with verified role
        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]
        
        # Mock guild get_role
        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        
        bot.get_member_or_user.return_value = user

        existing_report = MinorReport(
            id=1,
            user_id=2,
            reporter_id=3,
            suspected_age=15,
            evidence="Previous evidence",
            report_message_id=99999,
            status="pending"
        )

        with (
            patch('src.cmds.core.flag_minor.get_htb_user_id_for_discord', new_callable=AsyncMock) as get_link_mock,
            patch('src.cmds.core.flag_minor.get_account_identifier_for_discord', new_callable=AsyncMock) as get_acct_mock,
            patch('src.cmds.core.flag_minor.check_parental_consent', new_callable=AsyncMock) as consent_mock,
            patch('src.cmds.core.flag_minor.get_active_minor_report', new_callable=AsyncMock) as get_report_mock,
            patch('src.cmds.core.flag_minor.settings') as mock_settings
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = 999

            get_link_mock.return_value = None
            get_acct_mock.return_value = None
            get_report_mock.return_value = existing_report

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(
                cog, ctx, user, 15, "User stated they are 15 in chat"
            )

            assert ctx.respond.called

    @pytest.mark.asyncio
    async def test_flag_minor_invalid_age(self, ctx, bot):
        """Test flagging with an invalid age (outside 1-17 range)."""
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        user = helpers.MockMember(id=2, name="User")
        bot.get_member_or_user.return_value = user

        cog = flag_minor.FlagMinorCog(bot)

        # Test age too low - should respond with error
        await cog.flag_minor.callback(
            cog, ctx, user, 0, "Evidence"
        )
        # The command validates age and returns early with error
        assert ctx.respond.called or ctx.followup.send.called

        # Test age too high
        ctx.reset_mock()
        await cog.flag_minor.callback(
            cog, ctx, user, 18, "Evidence"
        )
        # The command validates age and returns early with error
        assert ctx.respond.called or ctx.followup.send.called

    @pytest.mark.asyncio
    async def test_flag_minor_no_account_identifier(self, ctx, bot):
        """Test early return when user has no linked HTB account."""
        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")
        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]
        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        bot.get_member_or_user.return_value = user

        status_edit = AsyncMock()
        ctx.respond.return_value = MagicMock(edit=status_edit)

        with (
            patch('src.cmds.core.flag_minor.get_htb_user_id_for_discord', new_callable=AsyncMock) as get_link_mock,
            patch('src.cmds.core.flag_minor.get_account_identifier_for_discord', new_callable=AsyncMock) as get_acct_mock,
            patch('src.cmds.core.flag_minor.check_parental_consent', new_callable=AsyncMock),
            patch('src.cmds.core.flag_minor.get_active_minor_report', new_callable=AsyncMock),
            patch('src.cmds.core.flag_minor.settings') as mock_settings
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            get_link_mock.return_value = None
            get_acct_mock.return_value = None  # No linked account

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(cog, ctx, user, 15, "Evidence")

            assert ctx.respond.called
            status_edit.assert_called_once()
            call_args = status_edit.call_args[1]
            assert "Could not find linked HTB account" in call_args.get("content", "")

    @pytest.mark.asyncio
    async def test_flag_minor_no_review_channel_configured(self, ctx, bot):
        """Test early return when MINOR_REVIEW channel is not configured."""
        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")
        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]
        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        bot.get_member_or_user.return_value = user

        status_edit = AsyncMock()
        ctx.respond.return_value = MagicMock(edit=status_edit)

        with (
            patch('src.cmds.core.flag_minor.get_htb_user_id_for_discord', new_callable=AsyncMock),
            patch('src.cmds.core.flag_minor.get_account_identifier_for_discord', new_callable=AsyncMock) as get_acct_mock,
            patch('src.cmds.core.flag_minor.check_parental_consent', new_callable=AsyncMock) as consent_mock,
            patch('src.cmds.core.flag_minor.get_active_minor_report', new_callable=AsyncMock),
            patch('src.cmds.core.flag_minor.settings') as mock_settings
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = None  # Not configured
            get_acct_mock.return_value = "some-uuid"
            consent_mock.return_value = False

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(cog, ctx, user, 15, "Evidence")

            status_edit.assert_called_once()
            assert "not configured" in status_edit.call_args[1].get("content", "").lower()

    @pytest.mark.asyncio
    async def test_flag_minor_review_channel_not_found(self, ctx, bot):
        """Test early return when review channel ID is set but channel not found."""
        verified_role = helpers.MockRole(id=123, name="Verified")
        minor_role = helpers.MockRole(id=456, name="Verified Minor")
        user = helpers.MockMember(id=2, name="Suspected Minor")
        user.roles = [verified_role]
        ctx.guild.get_role = lambda id: verified_role if id == 123 else minor_role if id == 456 else None
        ctx.guild.get_channel = MagicMock(return_value=None)  # Channel not found
        bot.get_member_or_user.return_value = user

        status_edit = AsyncMock()
        ctx.respond.return_value = MagicMock(edit=status_edit)

        with (
            patch('src.cmds.core.flag_minor.get_htb_user_id_for_discord', new_callable=AsyncMock),
            patch('src.cmds.core.flag_minor.get_account_identifier_for_discord', new_callable=AsyncMock) as get_acct_mock,
            patch('src.cmds.core.flag_minor.check_parental_consent', new_callable=AsyncMock) as consent_mock,
            patch('src.cmds.core.flag_minor.get_active_minor_report', new_callable=AsyncMock),
            patch('src.cmds.core.flag_minor.settings') as mock_settings
        ):
            mock_settings.roles.VERIFIED = 123
            mock_settings.roles.VERIFIED_MINOR = 456
            mock_settings.channels.MINOR_REVIEW = 999
            get_acct_mock.return_value = "some-uuid"
            consent_mock.return_value = False

            cog = flag_minor.FlagMinorCog(bot)
            await cog.flag_minor.callback(cog, ctx, user, 15, "Evidence")

            status_edit.assert_called_once()
            assert "not found" in status_edit.call_args[1].get("content", "").lower()

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        flag_minor.setup(bot)
        bot.add_cog.assert_called_once()
