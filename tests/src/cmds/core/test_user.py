from unittest.mock import AsyncMock, patch

import pytest

from src.cmds.core import user
from tests import helpers


class TestUserCog:
    """Test the `User` cog."""

    @pytest.mark.asyncio
    async def test_kick_success(self, ctx, guild, bot, session):
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        user_to_kick = helpers.MockMember(id=2, name="User to Kick", bot=False)
        ctx.guild = guild
        ctx.guild.kick = AsyncMock()
        bot.get_member_or_user = AsyncMock(return_value=user_to_kick)

        # Mock the DM channel
        user_to_kick.send = AsyncMock()
        user_to_kick.name = "User to Kick"

        with (
            patch('src.cmds.core.user.add_infraction', new_callable=AsyncMock) as add_infraction_mock,
            patch('src.cmds.core.user.member_is_staff', return_value=False)
        ):
            cog = user.UserCog(bot)
            await cog.kick.callback(cog, ctx, user_to_kick, "Violation of rules")

            reason = "Violation of rules"
            add_infraction_mock.assert_called_once_with(
                ctx.guild, user_to_kick, 0, f"Previously kicked for: {reason} - Evidence: None", ctx.user
            )

            # Assertions
            ctx.guild.kick.assert_called_once_with(user=user_to_kick, reason="Violation of rules")
            ctx.respond.assert_called_once_with("User to Kick got the boot!")

    @pytest.mark.asyncio
    async def test_kick_fail_user_left(self, ctx, guild, bot, session):
        ctx.user = helpers.MockMember(id=1, name="Test Moderator")
        user_to_kick = helpers.MockMember(id=2, name="User to Kick", bot=False)
        ctx.guild = guild
        ctx.guild.kick = AsyncMock()
        bot.get_member_or_user = AsyncMock(return_value=None)

        # Ensure the member_is_staff mock doesn't block execution
        with patch('src.cmds.core.user.member_is_staff', return_value=False):
            cog = user.UserCog(bot)
            await cog.kick.callback(cog, ctx, user_to_kick, "Violation of rules")

            # Assertions
            bot.get_member_or_user.assert_called_once_with(ctx.guild, user_to_kick.id)
            ctx.guild.kick.assert_not_called()  # No kick should occur
            ctx.respond.assert_called_once_with("User seems to have already left the server.")


    @pytest.mark.asyncio
    async def test_user_stats(self, ctx, bot):
        """Test the user_stats command displays correct statistics."""
        # Create mock members: 3 regular users (2 verified with roles, 1 unverified), 1 bot
        verified_member1 = helpers.MockMember(id=1, name="Verified1", bot=False)
        verified_member1.roles = [helpers.MockRole(id=0, name="@everyone"), helpers.MockRole(id=1, name="Verified")]

        verified_member2 = helpers.MockMember(id=2, name="Verified2", bot=False)
        verified_member2.roles = [helpers.MockRole(id=0, name="@everyone"), helpers.MockRole(id=2, name="Member")]

        unverified_member = helpers.MockMember(id=3, name="Unverified", bot=False)
        unverified_member.roles = [helpers.MockRole(id=0, name="@everyone")]

        bot_member = helpers.MockMember(id=4, name="BotUser", bot=True)

        ctx.guild.members = [verified_member1, verified_member2, unverified_member, bot_member]
        ctx.user = helpers.MockMember(id=100, name="Admin")
        ctx.channel = helpers.MockTextChannel(name="admin-channel")

        cog = user.UserCog(bot)
        await cog.user_stats.callback(cog, ctx)

        # Verify respond was called with an embed
        ctx.respond.assert_called_once()
        call_kwargs = ctx.respond.call_args[1]
        embed = call_kwargs["embed"]

        # Verify embed fields: 3 members, 2 verified (66.67%), 1 bot
        assert embed.title == "HackTheBox Discord User Stats"
        fields = {f.name: f.value for f in embed.fields}
        assert fields["Members"] == "3"
        assert fields["Bots"] == "1"
        assert "66.67%" in fields["Verified Members"]

    # ── _match_role tests ──────────────────────────────────────────────

    def test_match_role_no_role_manager(self, bot):
        """Test _match_role when role_manager is None."""
        bot.role_manager = None
        cog = user.UserCog(bot)
        role_id, err = cog._match_role("anything")
        assert role_id is None
        assert "don't know what role" in err

    def test_match_role_no_match(self, bot):
        """Test _match_role when no joinable role matches."""
        bot.role_manager.get_joinable_roles = lambda: {"Alpha": (111, "Alpha desc")}
        cog = user.UserCog(bot)
        role_id, err = cog._match_role("zzz_nonexistent")
        assert role_id is None
        assert "don't know what role" in err

    def test_match_role_single_match(self, bot):
        """Test _match_role with exactly one match."""
        bot.role_manager.get_joinable_roles = lambda: {"PenTesting": (222, "Pen desc")}
        cog = user.UserCog(bot)
        role_id, err = cog._match_role("pentest")
        assert role_id == 222
        assert err is None

    def test_match_role_multiple_matches(self, bot):
        """Test _match_role when multiple roles match."""
        bot.role_manager.get_joinable_roles = lambda: {
            "Red Team": (111, "desc"),
            "Red Alert": (222, "desc"),
        }
        cog = user.UserCog(bot)
        role_id, err = cog._match_role("Red")
        assert role_id is None
        assert "multiple roles" in err.lower()

    # ── join command tests ───────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_join_empty_role_name_shows_list(self, ctx, bot):
        """Test /join with empty role name shows the joinable roles embed."""
        bot.role_manager.get_joinable_roles = lambda: {"Alpha": (111, "Alpha desc")}
        cog = user.UserCog(bot)
        await cog.join.callback(cog, ctx, role_name="")

        ctx.respond.assert_awaited_once()
        call_kwargs = ctx.respond.call_args[1]
        embed = call_kwargs["embed"]
        assert embed.author.name == "Join-able Roles"

    @pytest.mark.asyncio
    async def test_join_whitespace_role_name_shows_list(self, ctx, bot):
        """Test /join with whitespace-only role name shows the joinable roles embed."""
        bot.role_manager.get_joinable_roles = lambda: {}
        cog = user.UserCog(bot)
        await cog.join.callback(cog, ctx, role_name="   ")

        ctx.respond.assert_awaited_once()
        call_kwargs = ctx.respond.call_args[1]
        assert "embed" in call_kwargs

    @pytest.mark.asyncio
    async def test_join_unknown_role(self, ctx, bot):
        """Test /join with an unknown role name returns an error."""
        bot.role_manager.get_joinable_roles = lambda: {"Alpha": (111, "Alpha desc")}
        cog = user.UserCog(bot)
        await cog.join.callback(cog, ctx, role_name="zzz_no_match")

        ctx.respond.assert_awaited_once()
        assert "don't know what role" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_join_success(self, ctx, bot):
        """Test /join successfully adds the role."""
        guild_role = helpers.MockRole(id=111, name="Alpha")
        ctx.guild.get_role = lambda rid: guild_role if rid == 111 else None
        ctx.user = helpers.MockMember()
        ctx.user.add_roles = AsyncMock()
        bot.role_manager.get_joinable_roles = lambda: {"Alpha": (111, "Alpha desc")}

        cog = user.UserCog(bot)
        await cog.join.callback(cog, ctx, role_name="Alpha")

        ctx.user.add_roles.assert_awaited_once_with(guild_role)
        ctx.respond.assert_awaited_once()
        assert "Welcome to Alpha" in ctx.respond.call_args[0][0]

    # ── leave command tests ──────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_leave_unknown_role(self, ctx, bot):
        """Test /leave with an unknown role name returns an error."""
        bot.role_manager.get_joinable_roles = lambda: {"Alpha": (111, "Alpha desc")}
        cog = user.UserCog(bot)
        await cog.leave.callback(cog, ctx, role_name="zzz_no_match")

        ctx.respond.assert_awaited_once()
        assert "don't know what role" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_leave_success(self, ctx, bot):
        """Test /leave successfully removes the role."""
        guild_role = helpers.MockRole(id=111, name="Alpha")
        ctx.guild.get_role = lambda rid: guild_role if rid == 111 else None
        ctx.user = helpers.MockMember()
        ctx.user.remove_roles = AsyncMock()
        bot.role_manager.get_joinable_roles = lambda: {"Alpha": (111, "Alpha desc")}

        cog = user.UserCog(bot)
        await cog.leave.callback(cog, ctx, role_name="Alpha")

        ctx.user.remove_roles.assert_awaited_once_with(guild_role)
        ctx.respond.assert_awaited_once()
        assert "left Alpha" in ctx.respond.call_args[0][0]

    # ── joinable_role_autocomplete tests ─────────────────────────────

    @pytest.mark.asyncio
    async def test_joinable_role_autocomplete_no_role_manager(self):
        """Test autocomplete returns empty list when role_manager is None."""
        ac_ctx = helpers.MockContext()
        ac_ctx.bot = helpers.MockBot()
        ac_ctx.bot.role_manager = None
        ac_ctx.value = "test"

        result = await user.joinable_role_autocomplete(ac_ctx)
        assert result == []

    @pytest.mark.asyncio
    async def test_joinable_role_autocomplete_filters(self):
        """Test autocomplete filters results based on typed value."""
        ac_ctx = helpers.MockContext()
        ac_ctx.bot = helpers.MockBot()
        ac_ctx.bot.role_manager.get_joinable_roles = lambda: {
            "Red Team": (1, "desc"),
            "Blue Team": (2, "desc"),
            "Red Alert": (3, "desc"),
        }
        ac_ctx.value = "red"

        result = await user.joinable_role_autocomplete(ac_ctx)
        assert "Red Team" in result
        assert "Red Alert" in result
        assert "Blue Team" not in result

    @pytest.mark.asyncio
    async def test_joinable_role_autocomplete_empty_value(self):
        """Test autocomplete returns all roles when value is empty."""
        ac_ctx = helpers.MockContext()
        ac_ctx.bot = helpers.MockBot()
        ac_ctx.bot.role_manager.get_joinable_roles = lambda: {
            "Alpha": (1, "desc"),
            "Beta": (2, "desc"),
        }
        ac_ctx.value = ""

        result = await user.joinable_role_autocomplete(ac_ctx)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_joinable_role_autocomplete_none_value(self):
        """Test autocomplete handles None value gracefully."""
        ac_ctx = helpers.MockContext()
        ac_ctx.bot = helpers.MockBot()
        ac_ctx.bot.role_manager.get_joinable_roles = lambda: {"Alpha": (1, "desc")}
        ac_ctx.value = None

        result = await user.joinable_role_autocomplete(ac_ctx)
        assert len(result) == 1

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        user.setup(bot)

        bot.add_cog.assert_called_once()
