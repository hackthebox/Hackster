import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import ClientSession
from dateutil.relativedelta import relativedelta

from src.helpers.minor_verification import (
    APPROVED,
    CONSENT_VERIFIED,
    DENIED,
    PENDING,
    assign_minor_role,
    calculate_ban_duration,
    check_parental_consent,
    get_active_minor_report,
    get_htb_user_id_for_discord,
    get_minor_review_reviewer_ids,
    invalidate_reviewer_ids_cache,
    is_minor_review_moderator,
    years_until_18,
)
from src.database.models import MinorReport
from tests import helpers


class MockResponse:
    def __init__(self, status, text_data="", json_data=None):
        self.status = status
        self._text = text_data
        self._json = json_data or {}

    async def text(self):
        return self._text

    async def json(self, content_type=None):
        return self._json

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


class TestMinorVerificationHelpers:
    """Test the minor verification helper functions."""

    def test_years_until_18_minor(self):
        """Test years until 18 calculation for a minor."""
        assert years_until_18(15) == 3
        assert years_until_18(17) == 1
        assert years_until_18(10) == 8

    def test_years_until_18_invalid_age(self):
        """Test years until 18 raises ValueError for invalid ages."""
        with pytest.raises(ValueError, match="suspected_age must be between 1 and 17"):
            years_until_18(18)
        with pytest.raises(ValueError, match="suspected_age must be between 1 and 17"):
            years_until_18(0)
        with pytest.raises(ValueError, match="suspected_age must be between 1 and 17"):
            years_until_18(25)

    def test_calculate_ban_duration_minor(self):
        """Test ban duration calculation for minors."""
        now = datetime.now(timezone.utc)
        duration = calculate_ban_duration(15)
        expected_timestamp = int((now + relativedelta(years=3)).timestamp())
        assert abs(duration - expected_timestamp) < 86400

    def test_calculate_ban_duration_edge_cases(self):
        """Test ban duration edge cases."""
        now = datetime.now(timezone.utc)

        duration = calculate_ban_duration(17)
        expected_timestamp = int((now + relativedelta(years=1)).timestamp())
        assert abs(duration - expected_timestamp) < 86400

        with pytest.raises(ValueError, match="suspected_age must be between 1 and 17"):
            calculate_ban_duration(18)

        duration = calculate_ban_duration(1)
        expected_timestamp = int((now + relativedelta(years=17)).timestamp())
        assert abs(duration - expected_timestamp) < 86400

    @pytest.mark.asyncio
    async def test_check_parental_consent_exists(self):
        """Test successful consent check via Nexus when consent exists."""
        discord_id = 123456789012345678

        mock_response = MockResponse(
            status=200,
            text_data='{"exists": true}',
            json_data={"exists": True},
        )

        with (
            patch("src.helpers.minor_verification.settings") as mock_settings,
            patch.object(ClientSession, "post", return_value=mock_response),
        ):
            mock_settings.NEXUS_API_BASE_URL = "https://nexus.example.com/secret"
            mock_settings.NEXUS_API_TOKEN = "test_token"

            result = await check_parental_consent(discord_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_check_parental_consent_not_exists(self):
        """Test Nexus consent check when consent doesn't exist."""
        discord_id = 123456789012345678

        mock_response = MockResponse(
            status=200,
            text_data='{"exists": false}',
            json_data={"exists": False},
        )

        with (
            patch("src.helpers.minor_verification.settings") as mock_settings,
            patch.object(ClientSession, "post", return_value=mock_response),
        ):
            mock_settings.NEXUS_API_BASE_URL = "https://nexus.example.com/secret"
            mock_settings.NEXUS_API_TOKEN = "test_token"

            result = await check_parental_consent(discord_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_parental_consent_missing_url(self):
        """Test consent check returns False when NEXUS_API_BASE_URL is not set."""
        with patch("src.helpers.minor_verification.settings") as mock_settings:
            mock_settings.NEXUS_API_BASE_URL = None
            mock_settings.NEXUS_API_TOKEN = "test_token"

            result = await check_parental_consent(123456789012345678)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_parental_consent_missing_token(self):
        """Test consent check returns False when NEXUS_API_TOKEN is not set."""
        with patch("src.helpers.minor_verification.settings") as mock_settings:
            mock_settings.NEXUS_API_BASE_URL = "https://nexus.example.com/secret"
            mock_settings.NEXUS_API_TOKEN = None

            result = await check_parental_consent(123456789012345678)

        assert result is False

    @pytest.mark.asyncio
    async def test_check_parental_consent_http_error(self):
        """Test consent check returns False on non-200 HTTP response."""
        discord_id = 123456789012345678

        mock_response = MockResponse(status=500, text_data="Internal Server Error")

        with (
            patch("src.helpers.minor_verification.settings") as mock_settings,
            patch.object(ClientSession, "post", return_value=mock_response),
        ):
            mock_settings.NEXUS_API_BASE_URL = "https://nexus.example.com/secret"
            mock_settings.NEXUS_API_TOKEN = "test_token"

            result = await check_parental_consent(discord_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_htb_user_id_for_discord_found(self):
        """Test getting HTB user ID when link exists."""
        discord_id = 123456789
        htb_id = 999

        mock_link = type('obj', (object,), {'htb_user_id': htb_id})()
        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = mock_link

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with patch('src.helpers.minor_verification.AsyncSessionLocal', return_value=AsyncContextManager()):
            result = await get_htb_user_id_for_discord(discord_id)

        assert result == htb_id

    @pytest.mark.asyncio
    async def test_get_htb_user_id_for_discord_not_found(self):
        """Test getting HTB user ID when no link exists."""
        discord_id = 123456789

        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = None

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with patch('src.helpers.minor_verification.AsyncSessionLocal', return_value=AsyncContextManager()):
            result = await get_htb_user_id_for_discord(discord_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_minor_report_found(self):
        """Test getting active minor report when one exists."""
        user_id = 123456789

        mock_report = MinorReport(
            id=1,
            user_id=user_id,
            reporter_id=987654321,
            suspected_age=15,
            evidence="Evidence",
            report_message_id=111222333,
            status=PENDING
        )

        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = mock_report

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with patch('src.helpers.minor_verification.AsyncSessionLocal', return_value=AsyncContextManager()):
            result = await get_active_minor_report(user_id)

        assert result == mock_report
        assert result.user_id == user_id

    @pytest.mark.asyncio
    async def test_get_active_minor_report_not_found(self):
        """Test getting active minor report when none exists."""
        user_id = 123456789

        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = None

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with patch('src.helpers.minor_verification.AsyncSessionLocal', return_value=AsyncContextManager()):
            result = await get_active_minor_report(user_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_minor_review_reviewer_ids(self):
        """Test getting reviewer IDs."""
        # The function queries MinorReviewReviewer.user_id which returns just IDs, not objects
        mock_ids = [111, 222, 333]

        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = mock_ids

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with patch('src.helpers.minor_verification.AsyncSessionLocal', return_value=AsyncContextManager()):
            # Clear cache first
            invalidate_reviewer_ids_cache()
            result = await get_minor_review_reviewer_ids()

        assert result == (111, 222, 333)

    @pytest.mark.asyncio
    async def test_is_minor_review_moderator_true(self):
        """Test checking if user is a reviewer (positive case)."""
        user_id = 111

        mock_ids = [111, 222]

        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = mock_ids

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with patch('src.helpers.minor_verification.AsyncSessionLocal', return_value=AsyncContextManager()):
            # Clear cache
            invalidate_reviewer_ids_cache()
            result = await is_minor_review_moderator(user_id)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_minor_review_moderator_false(self):
        """Test checking if user is a reviewer (negative case)."""
        user_id = 999

        mock_ids = [111, 222]

        mock_scalars_result = MagicMock()
        mock_scalars_result.all.return_value = mock_ids

        mock_session = AsyncMock()
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with patch('src.helpers.minor_verification.AsyncSessionLocal', return_value=AsyncContextManager()):
            # Clear cache
            invalidate_reviewer_ids_cache()
            result = await is_minor_review_moderator(user_id)

        assert result is False

    def test_invalidate_reviewer_ids_cache(self):
        """Test invalidating the reviewer cache."""
        # This function just resets the cache, so we can call it and ensure no errors
        invalidate_reviewer_ids_cache()
        # If it doesn't raise an exception, the test passes

    def test_status_constants(self):
        """Test that status constants are defined correctly."""
        assert PENDING == "pending"
        assert APPROVED == "approved"
        assert DENIED == "denied"
        assert CONSENT_VERIFIED == "consent_verified"

    @pytest.mark.asyncio
    async def test_assign_minor_role_success(self):
        """Test assigning minor role when member does not have it."""
        member = helpers.MockMember(id=1, name="User")
        guild = helpers.MockGuild()
        role = helpers.MockRole(id=456, name="Verified Minor")
        member.roles = []
        member.add_roles = AsyncMock()
        guild.get_role = lambda id: role if id == 456 else None

        with patch('src.helpers.minor_verification.settings') as mock_settings:
            mock_settings.roles.VERIFIED_MINOR = 456
            result = await assign_minor_role(member, guild)

        assert result is True
        member.add_roles.assert_called_once_with(role, atomic=True)

    @pytest.mark.asyncio
    async def test_assign_minor_role_already_has_role(self):
        """Test assign_minor_role when member already has the role."""
        role = helpers.MockRole(id=456, name="Verified Minor")
        member = helpers.MockMember(id=1, name="User")
        member.roles = [role]
        member.add_roles = AsyncMock()
        guild = helpers.MockGuild()
        guild.get_role = lambda id: role if id == 456 else None

        with patch('src.helpers.minor_verification.settings') as mock_settings:
            mock_settings.roles.VERIFIED_MINOR = 456
            result = await assign_minor_role(member, guild)

        assert result is False
        member.add_roles.assert_not_called()

    @pytest.mark.asyncio
    async def test_assign_minor_role_role_not_found(self):
        """Test assign_minor_role when guild does not have the role."""
        member = helpers.MockMember(id=1, name="User")
        guild = helpers.MockGuild()
        guild.get_role = lambda id: None

        with patch('src.helpers.minor_verification.settings') as mock_settings:
            mock_settings.roles.VERIFIED_MINOR = 456
            result = await assign_minor_role(member, guild)

        assert result is False

    @pytest.mark.asyncio
    async def test_assign_minor_role_forbidden(self):
        """Test assign_minor_role when add_roles raises Forbidden."""
        from discord import Forbidden

        member = helpers.MockMember(id=1, name="User")
        member.roles = []
        fake_response = MagicMock(status=403)
        member.add_roles = AsyncMock(side_effect=Forbidden(fake_response, "Forbidden"))
        role = helpers.MockRole(id=456, name="Verified Minor")
        guild = helpers.MockGuild()
        guild.get_role = lambda id: role if id == 456 else None

        with patch('src.helpers.minor_verification.settings') as mock_settings:
            mock_settings.roles.VERIFIED_MINOR = 456
            result = await assign_minor_role(member, guild)

        assert result is False
