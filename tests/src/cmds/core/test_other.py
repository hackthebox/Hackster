from unittest.mock import patch

import pytest

from src.cmds.core import other
from tests.helpers import MockTextChannel


class TestOther:
    """Test the `ChannelManage` cog."""

    @pytest.mark.asyncio
    async def test_no_hints(self, bot, ctx):
        """Test the response of the `no_hints` command."""
        cog = other.OtherCog(bot)

        # Invoke the command.
        await cog.no_hints.callback(cog, ctx)

        args, kwargs = ctx.channel.send.call_args
        content = args[0]

        # Command should respond with an embed.
        assert isinstance(content, str)

        assert content.startswith("No hints are allowed")

    @pytest.mark.asyncio
    async def test_spoiler_without_url(self, bot, ctx):
        """Test the response of the `spoiler` command without url."""
        cog = other.OtherCog(bot)

        # Invoke the command.
        await cog.spoiler.callback(cog, ctx, url="")

        args, kwargs = ctx.respond.call_args
        content = args[0]

        assert isinstance(content, str)

        assert content == "Please provide the spoiler URL."

    @pytest.mark.asyncio
    async def test_spoiler(self, bot, ctx):
        """Test the response of the `spoiler` command."""
        cog = other.OtherCog(bot)
        mock_channel = MockTextChannel()

        with patch.object(bot, "get_channel", return_value=mock_channel):
            # Invoke the command.
            await cog.spoiler.callback(cog, ctx, "https://www.definitely-a-spoiler.com/")

        args, kwargs = ctx.respond.call_args
        content = args[0]
        ephemeral = kwargs.get("ephemeral")
        delete_after = kwargs.get("delete_after")

        # Command should respond with an embed.
        assert mock_channel.send.call_count == 1
        assert isinstance(content, str)
        assert isinstance(ephemeral, bool)
        assert isinstance(delete_after, int)

        assert content == "Thanks for the reporting the spoiler."
        assert ephemeral is True
        assert delete_after == 15

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        other.setup(bot)

        bot.add_cog.assert_called_once()
