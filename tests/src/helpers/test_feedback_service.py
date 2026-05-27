from unittest.mock import AsyncMock, patch

import pytest

from src.helpers import feedback_service


class TestFeedbackServiceHelper:
    @pytest.mark.asyncio
    async def test_ingest_discord_feedback_success(self):
        with (
            patch.object(
                feedback_service.settings,
                "FEEDBACK_SERVICE_URL",
                "http://feedback.test/api/ingest/discord",
            ),
            patch.object(feedback_service.settings, "FEEDBACK_SERVICE_API_KEY", "test-key"),
            patch("aiohttp.ClientSession.post") as mock_post,
        ):
            mock_response = AsyncMock()
            mock_response.status = 202
            mock_post.return_value.__aenter__.return_value = mock_response

            await feedback_service.ingest_discord_feedback({"title": "Test"})

            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["headers"] == {"Authorization": "Bearer test-key"}
            assert call_kwargs["json"] == {"title": "Test"}

    @pytest.mark.asyncio
    async def test_ingest_skipped_when_not_configured(self):
        with (
            patch.object(feedback_service.settings, "FEEDBACK_SERVICE_URL", ""),
            patch.object(feedback_service.settings, "FEEDBACK_SERVICE_API_KEY", ""),
            patch("aiohttp.ClientSession.post") as mock_post,
        ):
            await feedback_service.ingest_discord_feedback({"title": "Test"})
            mock_post.assert_not_called()
