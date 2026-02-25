"""Tests for the MinorReviewers cog (parental consent feature)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cmds.core import minor_reviewers
from src.database.models import MinorReviewReviewer
from tests import helpers


class TestMinorReviewersCog:
    """Test the MinorReviewers cog."""

    @pytest.mark.asyncio
    async def test_add_success(self, ctx):
        """Test adding a reviewer when not already in list."""
        ctx.user = helpers.MockMember(id=1, name="Admin")
        user = helpers.MockMember(id=2, name="New Reviewer")

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = None
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with (
            patch('src.cmds.core.minor_reviewers.AsyncSessionLocal', return_value=AsyncContextManager()),
            patch('src.cmds.core.minor_reviewers.invalidate_reviewer_ids_cache') as invalidate_mock
        ):
            cog = minor_reviewers.MinorReviewersCog(AsyncMock())
            await cog.add.callback(cog, ctx, user)

            ctx.respond.assert_called_once()
            call_args = ctx.respond.call_args[0][0]
            assert "Added" in call_args and "reviewer" in call_args
            invalidate_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_already_exists(self, ctx):
        """Test adding a reviewer who is already in the list."""
        ctx.user = helpers.MockMember(id=1, name="Admin")
        user = helpers.MockMember(id=2, name="Existing Reviewer")
        existing = MinorReviewReviewer(
            id=1, user_id=2, added_by=1, created_at=datetime.now(timezone.utc)
        )

        mock_session = MagicMock()
        mock_session.add = MagicMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = existing
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with patch('src.cmds.core.minor_reviewers.AsyncSessionLocal', return_value=AsyncContextManager()):
            cog = minor_reviewers.MinorReviewersCog(AsyncMock())
            await cog.add.callback(cog, ctx, user)

            ctx.respond.assert_called_once()
            assert "already" in ctx.respond.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_remove_success(self, ctx):
        """Test removing a reviewer."""
        ctx.user = helpers.MockMember(id=1, name="Admin")
        user = helpers.MockMember(id=2, name="Reviewer")
        row = MinorReviewReviewer(
            id=1, user_id=2, added_by=1, created_at=datetime.now(timezone.utc)
        )

        mock_session = MagicMock()
        mock_session.delete = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = row
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with (
            patch('src.cmds.core.minor_reviewers.AsyncSessionLocal', return_value=AsyncContextManager()),
            patch('src.cmds.core.minor_reviewers.invalidate_reviewer_ids_cache') as invalidate_mock
        ):
            cog = minor_reviewers.MinorReviewersCog(AsyncMock())
            await cog.remove.callback(cog, ctx, user)

            ctx.respond.assert_called_once()
            assert "Removed" in ctx.respond.call_args[0][0]
            invalidate_mock.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_not_in_list(self, ctx):
        """Test removing a user who is not in the reviewer list."""
        ctx.user = helpers.MockMember(id=1, name="Admin")
        user = helpers.MockMember(id=2, name="User")

        mock_session = MagicMock()
        mock_scalars_result = MagicMock()
        mock_scalars_result.first.return_value = None
        mock_session.scalars = AsyncMock(return_value=mock_scalars_result)

        class AsyncContextManager:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc, tb):
                pass

        with patch('src.cmds.core.minor_reviewers.AsyncSessionLocal', return_value=AsyncContextManager()):
            cog = minor_reviewers.MinorReviewersCog(AsyncMock())
            await cog.remove.callback(cog, ctx, user)

            ctx.respond.assert_called_once()
            assert "not" in ctx.respond.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_list_reviewers_empty(self, ctx):
        """Test list when no reviewers configured."""
        with patch(
            'src.cmds.core.minor_reviewers.get_minor_review_reviewer_ids',
            new_callable=AsyncMock,
            return_value=(),
        ):
            cog = minor_reviewers.MinorReviewersCog(AsyncMock())
            await cog.list_reviewers.callback(cog, ctx)

            ctx.respond.assert_called_once()
            assert "no" in ctx.respond.call_args[0][0].lower() or "empty" in ctx.respond.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_list_reviewers_with_ids(self, ctx):
        """Test list when reviewers exist."""
        with patch(
            'src.cmds.core.minor_reviewers.get_minor_review_reviewer_ids',
            new_callable=AsyncMock,
            return_value=(111, 222),
        ):
            cog = minor_reviewers.MinorReviewersCog(AsyncMock())
            await cog.list_reviewers.callback(cog, ctx)

            ctx.respond.assert_called_once()
            assert "111" in ctx.respond.call_args[0][0] and "222" in ctx.respond.call_args[0][0]

    def test_setup(self, bot):
        """Test cog setup."""
        minor_reviewers.setup(bot)
        bot.add_cog.assert_called_once()
