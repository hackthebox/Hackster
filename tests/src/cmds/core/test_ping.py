import pytest
from discord import Embed

from src.cmds.core import ping
from src.utils.formatters import color_level


class TestPing:
    """Test the `Ping` cog."""

    @pytest.mark.asyncio
    async def test_ping(self, bot, ctx):
        """Test the response of the `ping` command."""
        bot.latency = 0.150  # Required by the command.
        cog = ping.PingCog(bot)

        # Invoke the command.
        await cog.ping.callback(cog, ctx)

        args, kwargs = ctx.respond.call_args
        embed: Embed = kwargs.get("embed")

        # Command should respond with an embed.
        assert isinstance(embed, Embed)

        # Colours' values should match.
        assert embed.colour.value == color_level(bot.latency)

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        ping.setup(bot)

        bot.add_cog.assert_called_once()
