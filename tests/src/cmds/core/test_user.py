from unittest.mock import AsyncMock, patch

import pytest

from src.cmds.core import user
from tests import helpers


class TestUserCog:
    """Test the `User` cog."""

    @pytest.mark.asyncio
    async def test_kick_success(self, ctx, bot):
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        user_to_kick = helpers.MockMember(id=2, name="User to Kick", bot=False)
        ctx.guild.kick = AsyncMock()
        bot.get_member_or_user = AsyncMock(return_value=user_to_kick)

        # Mock the DM channel
        user_to_kick.send = AsyncMock()
        user_to_kick.name = "User to Kick"

        with patch('src.cmds.core.user.add_evidence_note', new_callable=AsyncMock) as add_evidence_mock, \
                patch('src.cmds.core.user.member_is_staff', return_value=False):
            cog = user.UserCog(bot)
            await cog.kick.callback(cog, ctx, user_to_kick, "Violation of rules")

            add_evidence_mock.assert_called_once_with(user_to_kick.id, "kick", "Violation of rules", None, ctx.user.id)

            # Assertions
            ctx.guild.kick.assert_called_once_with(user=user_to_kick, reason="Violation of rules")
            ctx.respond.assert_called_once_with("User to Kick got the boot!")


    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        user.setup(bot)

        bot.add_cog.assert_called_once()
