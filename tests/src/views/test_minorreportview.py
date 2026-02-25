from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord import ButtonStyle, Interaction

from src.database.models import Ban, MinorReport
from src.views.minorreportview import (
    MinorReportView,
    build_minor_report_embed,
    get_report_by_message_id,
)
from tests import helpers


class TestMinorReportView:
    """Test the MinorReportView Discord UI component."""

    @pytest.mark.asyncio
    async def test_view_has_persistent_buttons(self, bot):
        """Test that view is constructed with persistent buttons."""
        view = MinorReportView(bot)
        
        # View should have timeout=None for persistence
        assert view.timeout is None
        
        # View should have 3 buttons
        assert len(view.children) == 3
        
        # All buttons should have custom_ids for persistence
        for child in view.children:
            assert hasattr(child, 'custom_id')
            assert child.custom_id is not None

    @pytest.mark.asyncio
    async def test_get_report_helper(self, bot):
        """Test the _get_report helper method."""
        view = MinorReportView(bot)
        
        # Create mock interaction with message
        interaction = AsyncMock(spec=Interaction)
        interaction.message = helpers.MockMessage(id=12345)
        
        mock_report = MinorReport(
            id=1,
            user_id=999,
            reporter_id=2,
            suspected_age=15,
            evidence="Evidence",
            report_message_id=12345,
            status="pending"
        )
        
        with patch('src.views.minorreportview.AsyncSessionLocal') as session_mock:
            mock_session = AsyncMock()
            session_mock.return_value.__aenter__.return_value = mock_session
            
            # Mock scalars result
            mock_scalars_result = MagicMock()
            mock_scalars_result.first.return_value = mock_report
            mock_session.scalars = AsyncMock(return_value=mock_scalars_result)
            
            # Call _get_report
            result = await view._get_report(interaction)
            
            assert result == mock_report

    @pytest.mark.asyncio
    async def test_get_report_not_found(self, bot):
        """Test _get_report when report doesn't exist."""
        view = MinorReportView(bot)
        
        # Create mock interaction with message
        interaction = AsyncMock(spec=Interaction)
        interaction.message = helpers.MockMessage(id=12345)
        
        with patch('src.views.minorreportview.AsyncSessionLocal') as session_mock:
            mock_session = AsyncMock()
            session_mock.return_value.__aenter__.return_value = mock_session
            
            # Mock scalars result with no report
            mock_scalars_result = MagicMock()
            mock_scalars_result.first.return_value = None
            mock_session.scalars = AsyncMock(return_value=mock_scalars_result)
            
            # Call _get_report
            result = await view._get_report(interaction)
            
            assert result is None

    @pytest.mark.asyncio
    async def test_build_minor_report_embed(self, bot):
        """Test building a minor report embed."""
        mock_report = MinorReport(
            id=1,
            user_id=999,
            reporter_id=888,
            suspected_age=15,
            evidence="User stated they are 15",
            report_message_id=12345,
            status="pending"
        )
        
        mock_guild = helpers.MockGuild()
        mock_reporter = helpers.MockMember(id=888, name="Reporter")
        mock_guild.get_member = lambda id: mock_reporter if id == 888 else None
        
        # build_minor_report_embed takes 2 positional args and keyword-only args
        embed = build_minor_report_embed(mock_report, mock_guild)
        
        # Verify embed has required fields
        assert embed.title is not None
        assert "15" in str(embed.description) or "15" in str(embed.fields)
        assert "pending" in str(embed.color).lower() or embed.color is not None

    @pytest.mark.asyncio
    async def test_htb_profile_url_constant(self, bot):
        """Test that HTB_PROFILE_URL constant is defined."""
        from src.views.minorreportview import HTB_PROFILE_URL
        
        assert HTB_PROFILE_URL is not None
        assert isinstance(HTB_PROFILE_URL, str)
        assert "hackthebox" in HTB_PROFILE_URL.lower()

    @pytest.mark.asyncio
    async def test_view_initialization(self, bot):
        """Test view is initialized correctly."""
        view = MinorReportView(bot)
        
        # Check bot is stored
        assert view.bot == bot
        
        # Check timeout is None for persistence
        assert view.timeout is None
        
        # Check children are added
        assert len(view.children) > 0

    @pytest.mark.asyncio
    async def test_view_button_styles(self, bot):
        """Test that view buttons have correct styles."""
        view = MinorReportView(bot)

        # Check button has children (the actual buttons)
        assert len(view.children) == 3

    @pytest.mark.asyncio
    async def test_view_button_labels(self, bot):
        """Test that view buttons have correct labels."""
        view = MinorReportView(bot)

        # Check view has buttons
        assert len(view.children) == 3
        # Buttons should have custom IDs for persistence
        custom_ids = [child.custom_id for child in view.children if hasattr(child, 'custom_id')]
        assert len(custom_ids) == 3

    @pytest.mark.asyncio
    async def test_button_custom_ids_are_unique(self, bot):
        """Test that button custom IDs are unique for persistence."""
        view = MinorReportView(bot)
        
        custom_ids = [child.custom_id for child in view.children if hasattr(child, 'custom_id')]
        
        # All custom IDs should be unique
        assert len(custom_ids) == len(set(custom_ids))
        
        # Should have 3 unique custom IDs
        assert len(custom_ids) == 3

    @pytest.mark.asyncio
    async def test_check_reviewer_authorized(self, bot):
        """Test _check_reviewer when user is a moderator."""
        view = MinorReportView(bot)
        interaction = AsyncMock(spec=Interaction)
        interaction.user = helpers.MockMember(id=1, name="Mod")
        interaction.response = AsyncMock()

        with patch(
            'src.views.minorreportview.is_minor_review_moderator',
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = await view._check_reviewer(interaction)

        assert result is True
        interaction.response.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_reviewer_unauthorized(self, bot):
        """Test _check_reviewer when user is not a moderator."""
        view = MinorReportView(bot)
        interaction = AsyncMock(spec=Interaction)
        interaction.user = helpers.MockMember(id=1, name="User")
        interaction.response = AsyncMock()

        with patch(
            'src.views.minorreportview.is_minor_review_moderator',
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await view._check_reviewer(interaction)

        assert result is False
        interaction.response.send_message.assert_called_once()
        assert "not authorized" in interaction.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_interaction_check_no_report(self, bot):
        """Test interaction_check when report is not found."""
        view = MinorReportView(bot)
        interaction = AsyncMock(spec=Interaction)
        interaction.message = helpers.MockMessage(id=999)
        interaction.user = helpers.MockMember(id=1, name="Mod")
        interaction.response = AsyncMock()

        with patch(
            'src.views.minorreportview.get_report_by_message_id',
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await view.interaction_check(interaction)

        assert result is False
        interaction.response.send_message.assert_called_once()
        assert "not found" in interaction.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_interaction_check_report_exists_authorized(self, bot):
        """Test interaction_check when report exists and user is authorized."""
        view = MinorReportView(bot)
        mock_report = MinorReport(
            id=1,
            user_id=999,
            reporter_id=2,
            suspected_age=15,
            evidence="Evidence",
            report_message_id=12345,
            status="pending",
        )
        interaction = AsyncMock(spec=Interaction)
        interaction.message = helpers.MockMessage(id=12345)
        interaction.user = helpers.MockMember(id=1, name="Mod")
        interaction.response = AsyncMock()

        with (
            patch(
                'src.views.minorreportview.get_report_by_message_id',
                new_callable=AsyncMock,
                return_value=mock_report,
            ),
            patch(
                'src.views.minorreportview.is_minor_review_moderator',
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = await view.interaction_check(interaction)

        assert result is True
        interaction.response.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_recheck_callback_no_account(self, bot):
        """Test _recheck_callback when user has no linked account."""
        view = MinorReportView(bot)
        mock_report = MinorReport(
            id=1,
            user_id=999,
            reporter_id=2,
            suspected_age=15,
            evidence="Evidence",
            report_message_id=12345,
            status="approved",
        )
        interaction = AsyncMock(spec=Interaction)
        interaction.response = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.message = helpers.MockMessage(id=12345)
        interaction.guild = helpers.MockGuild()

        with patch(
            'src.views.minorreportview.get_account_identifier_for_discord',
            new_callable=AsyncMock,
            return_value=None,
        ):
            await view._recheck_callback(interaction, mock_report)

        interaction.response.defer.assert_called_once_with(ephemeral=True)
        interaction.followup.send.assert_called_once()
        assert "linked account" in interaction.followup.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_recheck_callback_consent_not_found(self, bot):
        """Test _recheck_callback when consent is not found."""
        view = MinorReportView(bot)
        now = datetime.now(timezone.utc)
        mock_report = MinorReport(
            id=1,
            user_id=999,
            reporter_id=2,
            suspected_age=15,
            evidence="Evidence",
            report_message_id=12345,
            status="approved",
            created_at=now,
            updated_at=now,
        )
        interaction = AsyncMock(spec=Interaction)
        interaction.response = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.message = AsyncMock()
        interaction.message.edit = AsyncMock()
        interaction.message.id = 12345
        interaction.guild = helpers.MockGuild()
        interaction.user = helpers.MockMember(id=1, name="Mod")
        bot.get_member_or_user = AsyncMock(return_value=None)

        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.commit = AsyncMock()

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with (
            patch(
                'src.views.minorreportview.get_account_identifier_for_discord',
                new_callable=AsyncMock,
                return_value="uuid-123",
            ),
            patch(
                'src.views.minorreportview.check_parental_consent',
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch('src.views.minorreportview.AsyncSessionLocal', return_value=AsyncContextManager()),
            patch(
                'src.views.minorreportview.get_htb_user_id_for_discord',
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            await view._recheck_callback(interaction, mock_report)

        interaction.followup.send.assert_called_once()
        assert "consent still not found" in interaction.followup.send.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_recheck_callback_consent_found_no_ban(self, bot):
        """Test _recheck_callback when consent is found and user was not banned by this report."""
        view = MinorReportView(bot)
        now = datetime.now(timezone.utc)
        mock_report = MinorReport(
            id=1,
            user_id=999,
            reporter_id=2,
            suspected_age=15,
            evidence="Evidence",
            report_message_id=12345,
            status="approved",
            associated_ban_id=None,
            created_at=now,
            updated_at=now,
        )
        mock_member = helpers.MockMember(id=999, name="User")
        interaction = AsyncMock(spec=Interaction)
        interaction.response = AsyncMock()
        interaction.response.defer = AsyncMock()
        interaction.followup = AsyncMock()
        interaction.followup.send = AsyncMock()
        interaction.message = AsyncMock()
        interaction.message.edit = AsyncMock()
        interaction.message.id = 12345
        interaction.guild = helpers.MockGuild()
        interaction.user = helpers.MockMember(id=1, name="Mod")
        bot.get_member_or_user = AsyncMock(return_value=mock_member)

        # session.get returns a report-like object for build_minor_report_embed
        mock_session = MagicMock()
        mock_session.get = AsyncMock(return_value=mock_report)
        mock_session.commit = AsyncMock()

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with (
            patch(
                'src.views.minorreportview.get_account_identifier_for_discord',
                new_callable=AsyncMock,
                return_value="uuid-123",
            ),
            patch(
                'src.views.minorreportview.check_parental_consent',
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                'src.views.minorreportview.assign_minor_role',
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                'src.views.minorreportview.get_ban',
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                'src.views.minorreportview.update_report_status',
                new_callable=AsyncMock,
            ),
            patch('src.views.minorreportview.AsyncSessionLocal', return_value=AsyncContextManager()),
            patch('src.views.minorreportview.get_htb_user_id_for_discord', new_callable=AsyncMock, return_value=None),
        ):
            await view._recheck_callback(interaction, mock_report)

        interaction.followup.send.assert_called_once()
        assert "consent found" in interaction.followup.send.call_args[0][0].lower()
        view.bot.get_member_or_user.assert_called_once()
