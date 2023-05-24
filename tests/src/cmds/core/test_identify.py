from src.cmds.core import identify


class TestIdentifyCog:
    """Test the `Identify` cog."""

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        identify.setup(bot)

        bot.add_cog.assert_called_once()
