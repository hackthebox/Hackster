from src.cmds.core import note


class TestNoteCog:
    """Test the `Note` cog."""

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        note.setup(bot)

        bot.add_cog.assert_called_once()
