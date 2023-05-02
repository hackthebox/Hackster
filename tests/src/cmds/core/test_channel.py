import pytest

from src.cmds.core import channel
from tests.helpers import MockTextChannel


class TestChannelManage:
    """Test the `ChannelManage` cog."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("seconds", [10, str(10)])
    async def test_slowmode_success(self, bot, ctx, seconds):
        """Test `slowmode` command with valid seconds."""
        cog = channel.ChannelCog(bot)

        channel_ = MockTextChannel(name="slow-mode")
        # Invoke the command.
        await cog.slowmode.callback(cog, ctx, channel=channel_, seconds=seconds)

        args, kwargs = ctx.respond.call_args
        content = args[0]

        # Assert channel was edited
        channel_.edit.assert_called_once_with(slowmode_delay=int(seconds))
        # Assert response was sent
        assert isinstance(content, str)
        assert content == f"Slow-mode set in {channel_.name} to {seconds} seconds."
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "seconds, expected_seconds", [(300, 30), (-10, 0)]
    )
    async def test_slowmode_with_seconds_out_of_bounds(self, bot, ctx, seconds, expected_seconds):
        """Test `slowmode` command without of bounds seconds."""
        cog = channel.ChannelCog(bot)

        channel_ = MockTextChannel(name="slow-mode")
        # Invoke the command.
        await cog.slowmode.callback(cog, ctx, channel=channel_, seconds=seconds)

        args, kwargs = ctx.respond.call_args
        content = args[0]

        # Assert channel was edited
        channel_.edit.assert_called_once_with(slowmode_delay=expected_seconds)
        # Assert response was sent
        assert isinstance(content, str)
        assert content == f"Slow-mode set in {channel_.name} to {expected_seconds} seconds."
        ctx.respond.assert_called_once()

    @pytest.mark.asyncio
    async def test_slowmode_seconds_as_invalid_string(self, bot, ctx):
        """Test the response of the `slowmode` command with invalid seconds string."""
        cog = channel.ChannelCog(bot)

        seconds = "not seconds"
        # Invoke the command.
        await cog.slowmode.callback(cog, ctx, channel=MockTextChannel(), seconds=seconds)

        args, kwargs = ctx.respond.call_args
        content = args[0]

        # Command should respond with a string.
        assert isinstance(content, str)
        assert content == f"Malformed amount of seconds: {seconds}."
        ctx.respond.assert_called_once()

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        channel.setup(bot)

        bot.add_cog.assert_called_once()
