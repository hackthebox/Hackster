from unittest import mock

import pytest

from src.cmds.automation import auto_verify
from tests import helpers


class TestMessageHandler:
    """Test the `MessageHandler` cog."""

    @pytest.mark.asyncio
    async def test_on_message_in_unverified_channel_sends_welcome(self, bot):
        """Test that a welcome message is sent when user posts in unverified channel."""
        cog = auto_verify.MessageHandler(bot)

        # Create a mock message in the specific unverified channel
        channel = helpers.MockTextChannel(id=1430556712313688225)
        author = helpers.MockMember(bot=False)
        message = helpers.MockMessage(channel=channel, author=author)
        message.reply = mock.AsyncMock()

        await cog.on_message(message)

        # Verify reply was called with welcome message
        message.reply.assert_called_once()
        call_args = message.reply.call_args
        assert "Welcome to the Hack The Box Discord" in call_args[0][0]
        assert call_args[1]["mention_author"] is True

    @pytest.mark.asyncio
    async def test_on_message_in_other_channel_no_welcome(self, bot):
        """Test that no welcome is sent in other channels."""
        cog = auto_verify.MessageHandler(bot)

        # Create a mock message in a different channel
        channel = helpers.MockTextChannel(id=999999999999999999)
        author = helpers.MockMember(bot=False)
        message = helpers.MockMessage(channel=channel, author=author)
        message.reply = mock.AsyncMock()

        await cog.on_message(message)

        # Verify reply was NOT called
        message.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_message_from_bot_returns_early(self, bot):
        """Test that bot messages are ignored."""
        cog = auto_verify.MessageHandler(bot)

        # Create a message from a bot in the unverified channel
        channel = helpers.MockTextChannel(id=1430556712313688225)
        author = helpers.MockMember(bot=True)
        message = helpers.MockMessage(channel=channel, author=author)
        message.reply = mock.AsyncMock()

        await cog.on_message(message)

        # Reply should not be called for bot messages
        message.reply.assert_not_called()
