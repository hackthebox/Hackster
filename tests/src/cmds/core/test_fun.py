from src.cmds.core import fun


class TestFunCog:
    """Test the `Fun` cog."""

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        fun.setup(bot)

        bot.add_cog.assert_called_once()
