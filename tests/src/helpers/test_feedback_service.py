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

            result = await feedback_service.ingest_discord_feedback({"title": "Test"})

            assert result is True
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args.kwargs
            assert call_kwargs["headers"] == {"Authorization": "Bearer test-key"}
            assert call_kwargs["json"] == {"title": "Test"}

    @pytest.mark.asyncio
    async def test_ingest_returns_false_when_not_configured(self):
        with (
            patch.object(feedback_service.settings, "FEEDBACK_SERVICE_URL", ""),
            patch.object(feedback_service.settings, "FEEDBACK_SERVICE_API_KEY", ""),
            patch("aiohttp.ClientSession.post") as mock_post,
        ):
            result = await feedback_service.ingest_discord_feedback({"title": "Test"})

            assert result is False
            mock_post.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_returns_false_on_non_202_response(self):
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
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_post.return_value.__aenter__.return_value = mock_response

            result = await feedback_service.ingest_discord_feedback({"title": "Test"})

            assert result is False

    @pytest.mark.asyncio
    async def test_ingest_returns_false_on_request_exception(self):
        with (
            patch.object(
                feedback_service.settings,
                "FEEDBACK_SERVICE_URL",
                "http://feedback.test/api/ingest/discord",
            ),
            patch.object(feedback_service.settings, "FEEDBACK_SERVICE_API_KEY", "test-key"),
            patch("aiohttp.ClientSession.post", side_effect=TimeoutError("timed out")),
        ):
            result = await feedback_service.ingest_discord_feedback({"title": "Test"})

            assert result is False
