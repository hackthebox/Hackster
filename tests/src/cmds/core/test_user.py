import calendar
import time
from datetime import date
from unittest import mock
from unittest.mock import AsyncMock, patch

import pytest

from src.bot import Bot
from src.cmds.core import user
from src.database.models import Ban, Infraction
from src.helpers.duration import parse_duration_str
from src.helpers.responses import SimpleResponse
from tests import helpers


class TestUserCog:
    """Test the `User` cog."""

    @pytest.mark.asyncio
    async def test_kick_valid_case(self, ctx, bot, guild, member):
        ctx.user = helpers.MockMember(name="Author User")
        ctx.guild = guild
        ctx.bot = bot
        member.send = AsyncMock()
        reason = "Any valid reason"
        bot.get_member_or_user.return_value = member
        with patch.object(guild, "kick"):
            cog = user.UserCog(bot)
            await cog.kick.callback(cog, ctx, member, reason)
            ctx.guild.kick.assert_called_once_with(user=member, reason=reason)

        bot.get_member_or_user.assert_called_once_with(guild, member.id)
        member.send.assert_called_once_with(
            f"You have been kicked from {guild.name} for the following reason:\n>>> {reason}\n"
        )

    @pytest.mark.asyncio
    async def test_kick_user_not_found(self, ctx, bot, guild, member):
        ctx.user = helpers.MockMember(name="Author User")
        ctx.guild = guild
        ctx.bot = bot
        bot.get_member_or_user.return_value = None
        cog = user.UserCog(bot)
        await cog.kick.callback(cog, ctx, member, "Any valid reason")
        ctx.respond.assert_called_once_with(
            f"Member {member} not found. You cannot kick a user who is not in the server!"
        )

    @pytest.mark.asyncio
    async def test_kick_member_is_staff(self, ctx, bot, guild, member):
        ctx.user = helpers.MockMember(name="Author User")
        ctx.guild = guild
        ctx.bot = bot
        member_is_staff = mock.Mock(return_value=True)
        with mock.patch("src.cmds.core.user.member_is_staff", member_is_staff):
            cog = user.UserCog(bot)
            await cog.kick.callback(cog, ctx, member, "Any valid reason")
            ctx.respond.assert_called_once_with("You cannot kick another staff member.")

    def test_setup(self, bot: Bot) -> None:
        """Test the setup method of the cog."""
        # Invoke the command
        user.setup(bot)

        bot.add_cog.assert_called_once()
