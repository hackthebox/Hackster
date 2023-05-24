from src.cmds.core import history


class TestHistoryCog:
    """Test the `History` cog."""

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        history.setup(bot)

        bot.add_cog.assert_called_once()
