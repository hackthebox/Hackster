from src.cmds.dev import extensions


class TestExtensions:
    """Test the `Extensions` cog."""

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        extensions.setup(bot)

        bot.add_cog.assert_called_once()
