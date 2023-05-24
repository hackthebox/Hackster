from src.cmds.core import mute


class TestMuteCog:
    """Test the `Mute` cog."""

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        mute.setup(bot)

        bot.add_cog.assert_called_once()
