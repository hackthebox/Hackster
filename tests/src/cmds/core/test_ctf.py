from src.cmds.core import ctf


class TestCtfCog:
    """Test the `Ctf` cog."""

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        ctf.setup(bot)

        bot.add_cog.assert_called_once()
