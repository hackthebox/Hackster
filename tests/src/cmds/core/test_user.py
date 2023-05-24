from src.cmds.core import user


class TestUserCog:
    """Test the `User` cog."""

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        user.setup(bot)

        bot.add_cog.assert_called_once()
