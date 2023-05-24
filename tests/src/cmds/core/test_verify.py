from src.cmds.core import verify


class TestVerifyCog:
    """Test the `Verify` cog."""

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        verify.setup(bot)

        bot.add_cog.assert_called_once()
