import calendar
import time
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from discord import Forbidden

from src.cmds.core import ban
from src.database.models import Ban, Infraction
from src.helpers.ban import add_infraction
from src.helpers.duration import parse_duration_str
from src.helpers.responses import SimpleResponse
from tests import helpers


class MockResponse:
    def __init__(self, status):
        self.status = status
        self.reason = 'Forbidden'
        self.code = status
        self.text = "Cannot send messages to this user"

class TestBanCog:
    """Test the `Ban` cog."""

    @pytest.mark.asyncio
    async def test_ban_success(self, ctx, bot):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        user = helpers.MockMember(id=2, name="Banned User")
        bot.get_member_or_user.return_value = user

        with (
            patch('src.cmds.core.ban.ban_member', new_callable=AsyncMock) as ban_member_mock
        ):
            ban_response = SimpleResponse(
                message=f"Member {user.display_name} has been banned permanently.", delete_after=0
            )
            ban_member_mock.return_value = ban_response

            cog = ban.BanCog(bot)
            await cog.ban.callback(cog, ctx, user, "Any valid reason", "Some evidence")

            # Assertions
            ban_member_mock.assert_called_once_with(
                bot, ctx.guild, user, "500w", "Any valid reason", "Some evidence", ctx.user, needs_approval=False
            )
            ctx.respond.assert_called_once_with(
                f"Member {user.display_name} has been banned permanently.", delete_after=0
            )

    @pytest.mark.asyncio
    async def test_tempban_success(self, ctx, bot):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        user = helpers.MockMember(id=2, name="Banned User")
        bot.get_member_or_user.return_value = user

        with (
            patch('src.helpers.ban.validate_duration', new_callable=AsyncMock) as validate_duration_mock, \
            patch('src.cmds.core.ban.ban_member', new_callable=AsyncMock) as ban_member_mock
        ):
            validate_duration_mock.return_value = (calendar.timegm(time.gmtime()) + parse_duration_str("5d"), "")
            ban_response = SimpleResponse(
                message=f"Member {user.display_name} has been banned temporarily.", delete_after=0
            )
            ban_member_mock.return_value = ban_response

            cog = ban.BanCog(bot)
            await cog.tempban.callback(cog, ctx, user, "5d", "Any valid reason", "Some evidence")

            # Assertions
            ban_member_mock.assert_called_once_with(
                bot, ctx.guild, user, "5d", "Any valid reason", "Some evidence", ctx.user, needs_approval=True
            )
            ctx.respond.assert_called_once_with(
                f"Member {user.display_name} has been banned temporarily.", delete_after=0
            )

    @pytest.mark.asyncio
    async def test_tempban_failed_with_wrong_duration(self, ctx, bot, guild):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        ctx.guild = guild
        user = helpers.MockMember(id=2, name="Banned User")
        bot.get_member_or_user.return_value = user

        with (
            patch('src.helpers.ban.validate_duration', new_callable=AsyncMock) as validate_duration_mock,
            patch('src.cmds.core.ban.ban_member', new_callable=AsyncMock) as ban_member_mock
        ):
            validate_duration_mock.return_value = (
                0, "Malformed duration. Please use duration units, (e.g. 12h, 14d, 5w)."
            )
            ban_response = SimpleResponse(
                message="Malformed duration. Please use duration units, (e.g. 12h, 14d, 5w).", delete_after=15
            )
            ban_member_mock.return_value = ban_response

            cog = ban.BanCog(bot)
            await cog.tempban.callback(cog, ctx, user, "5", "Any valid reason", "Some evidence")

            # Assertions
            ban_member_mock.assert_called_once_with(
                bot, ctx.guild, user, "5", "Any valid reason", "Some evidence", ctx.user, needs_approval=True
            )
            ctx.respond.assert_called_once_with(
                "Malformed duration. Please use duration units, (e.g. 12h, 14d, 5w).", delete_after=15
            )

    @pytest.mark.asyncio
    async def test_unban_success(self, ctx, bot):
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        user = helpers.MockMember(id=2, name="Banned User")
        bot.get_member_or_user.return_value = user

        with patch('src.cmds.core.ban.unban_member', new_callable=AsyncMock) as unban_member_mock:
            unban_member_mock.return_value = user

            cog = ban.BanCog(bot)
            await cog.unban.callback(cog, ctx, user)

            # Assertions
            unban_member_mock.assert_called_once_with(ctx.guild, user)
            ctx.respond.assert_called_once_with(f"User #{user.id} has been unbanned.")

    @pytest.mark.asyncio
    async def test_unban_failure(self, ctx, bot):
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        user = helpers.MockMember(id=2, name="Banned User")
        bot.get_member_or_user.return_value = user

        with patch('src.cmds.core.ban.unban_member', new_callable=AsyncMock) as unban_member_mock:
            unban_member_mock.return_value = None

            cog = ban.BanCog(bot)
            await cog.unban.callback(cog, ctx, user)

            # Assertions
            unban_member_mock.assert_called_once_with(ctx.guild, user)
            ctx.respond.assert_called_once_with("Failed to unban user. Are they perhaps not banned at all?")

    @pytest.mark.asyncio
    async def test_deny_success(self, ctx, bot):
        # Define a mock ban record in the database
        ban_record = Ban(id=1, user_id=1, reason="No reason", moderator_id=2)

        async with AsyncMock() as mock:
            mock.get.return_value = ban_record

            with patch('src.cmds.core.ban.AsyncSessionLocal', return_value=mock):
                # Call the deny command and check the response
                cog = ban.BanCog(bot)
                await cog.deny.callback(cog, ctx, ban_record.id)

                ctx.respond.assert_called_once_with("Ban request denied. The user has been unbanned.")

    @pytest.mark.asyncio
    async def test_warn_success(self, ctx, bot):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        user = helpers.MockMember(id=2, name="Banned User")
        bot.get_member_or_user.return_value = user

        with patch('src.cmds.core.ban.add_infraction', new_callable=AsyncMock) as add_infraction_mock:
            add_infraction_mock.return_value = SimpleResponse(
                message=f"{user.mention} ({user.id}) has been warned with a strike weight of 0.",
                delete_after=None
            )
            cog = ban.BanCog(bot)
            await cog.warn.callback(cog, ctx, user, "Any valid reason")

            # Assertions
            add_infraction_mock.assert_called_once_with(ctx.guild, user, 0, "Any valid reason", ctx.user)

    @pytest.mark.asyncio
    async def test_warn_user_not_found(self, ctx, bot):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        user = helpers.MockMember(id=2, name="Banned User")
        bot.get_member_or_user.return_value = None

        cog = ban.BanCog(bot)
        await cog.warn.callback(cog, ctx, user, "Any valid reason")

        # Assertions
        ctx.respond.assert_called_once_with(f"User {user} not found.")

    @pytest.mark.asyncio
    async def test_strike_success(self, ctx, bot):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        user = helpers.MockMember(id=2, name="Banned User")
        bot.get_member_or_user.return_value = user

        with patch('src.cmds.core.ban.add_infraction', new_callable=AsyncMock) as add_infraction_mock:
            add_infraction_mock.return_value = SimpleResponse(
                message=f"{user.mention} ({user.id}) has been warned with a strike weight of 10.",
                delete_after=None
            )
            cog = ban.BanCog(bot)
            await cog.strike.callback(cog, ctx, user, 10, "Any valid reason")

            # Assertions
            add_infraction_mock.assert_called_once_with(ctx.guild, user, 10, "Any valid reason", ctx.user)

    @pytest.mark.asyncio
    async def test_strike_user_not_found(self, ctx, bot):
        ctx.user = helpers.MockMember(id=1, name="Test User")
        user = helpers.MockMember(id=2, name="Banned User")
        bot.get_member_or_user.return_value = None

        cog = ban.BanCog(bot)
        await cog.strike.callback(cog, ctx, user, 10, "Any valid reason")

        # Assertions
        ctx.respond.assert_called_once_with(f"User {user} not found.")

    @pytest.mark.asyncio
    async def test_remove_infraction_success(self, ctx, bot):
        # Define a mock ban record in the database
        infraction_record = Infraction(
            id=1, user_id=1, reason="No reason", weight=10, moderator_id=2, date=date.today()
        )

        async with AsyncMock() as mock:
            mock.get.return_value = infraction_record

            with patch('src.cmds.core.ban.AsyncSessionLocal', return_value=mock):
                # Call the remove_infraction command and check the response
                cog = ban.BanCog(bot)
                await cog.remove_infraction.callback(cog, ctx, infraction_record.id)

                ctx.respond.assert_called_once_with(f"Infraction record #{infraction_record.id} has been deleted.")


    @pytest.mark.asyncio
    async def test_add_infraction_success(self, ctx, guild, member, author, bot):
        member.send = AsyncMock()
        bot.get_member_or_user.return_value = member

        # Patch the AsyncSessionLocal to simulate database interaction
        async with AsyncMock() as mock_session:
            with patch('src.helpers.ban.AsyncSessionLocal', return_value=mock_session):
                response = await add_infraction(guild, member, 10, "Test infraction reason", author)

        # Assertions
        assert response.message == f"{member.mention} ({member.id}) has been warned with a strike weight of 10."
        member.send.assert_called_once_with(
            f"You have been warned on {guild.name} with a strike value of 10. "
            f"After a total value of 3, permanent exclusion from the server may be enforced.\n"
            f"Following is the reason given:\n>>> Test infraction reason\n"
        )

    @pytest.mark.asyncio
    async def test_add_infraction_dm_forbidden(self, ctx, guild, member, author, bot):
        member.send = AsyncMock(side_effect=Forbidden(
            response=MockResponse(403),
            message="Cannot send messages to this user"
        ))
        bot.get_member_or_user.return_value = member

        # Patch the AsyncSessionLocal to simulate database interaction
        async with AsyncMock() as mock_session:
            with patch('src.helpers.ban.AsyncSessionLocal', return_value=mock_session):
                response = await add_infraction(guild, member, 10, "Test infraction reason", author)

        # Assertions
        assert response.message == "Could not DM member due to privacy settings, however the infraction was still added."
        member.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_infraction_no_reason(self, ctx, guild, member, author, bot):
        member.send = AsyncMock()
        bot.get_member_or_user.return_value = member

        # Patch the AsyncSessionLocal to simulate database interaction
        async with AsyncMock() as mock_session:
            with patch('src.helpers.ban.AsyncSessionLocal', return_value=mock_session):
                response = await add_infraction(guild, member, 10, "", author)

        # Assertions
        assert response.message == f"{member.mention} ({member.id}) has been warned with a strike weight of 10."
        member.send.assert_called_once_with(
            f"You have been warned on {guild.name} with a strike value of 10. "
            f"After a total value of 3, permanent exclusion from the server may be enforced.\n"
            f"Following is the reason given:\n>>> No reason given ...\n"
        )

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        ban.setup(bot)

        bot.add_cog.assert_called_once()
