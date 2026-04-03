from unittest.mock import AsyncMock, MagicMock

import pytest

from src.cmds.core import role_admin
from src.cmds.core.role_admin import RoleAdminCog
from src.database.models.dynamic_role import RoleCategory
from tests import helpers


class TestRoleAdminCog:
    """Test the `RoleAdminCog` cog."""

    # ── add command ──────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_add_success(self, ctx, bot):
        """Test adding a dynamic role with valid parameters."""
        bot.role_manager.add_role = AsyncMock()
        discord_role = helpers.MockRole(id=9999, name="TestRole")

        cog = RoleAdminCog(bot)
        await cog.add.callback(
            cog,
            ctx,
            category="rank",
            key="Omniscient",
            role=discord_role,
            display_name="Omniscient Rank",
            description=None,
            cert_full_name=None,
            cert_integer_id=None,
        )

        bot.role_manager.add_role.assert_awaited_once_with(
            key="Omniscient",
            category=RoleCategory.RANK,
            discord_role_id=discord_role.id,
            display_name="Omniscient Rank",
            description=None,
            cert_full_name=None,
            cert_integer_id=None,
        )
        ctx.respond.assert_awaited_once()
        assert "Added dynamic role" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_add_invalid_category(self, ctx, bot):
        """Test adding a role with an invalid category returns an error."""
        discord_role = helpers.MockRole(id=9999, name="TestRole")

        cog = RoleAdminCog(bot)
        await cog.add.callback(
            cog,
            ctx,
            category="not_a_real_category",
            key="Key",
            role=discord_role,
            display_name="Display",
            description=None,
            cert_full_name=None,
            cert_integer_id=None,
        )

        ctx.respond.assert_awaited_once()
        assert "Invalid category" in ctx.respond.call_args[0][0]

    # ── remove command ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_remove_success(self, ctx, bot):
        """Test removing an existing dynamic role."""
        bot.role_manager.remove_role = AsyncMock(return_value=True)

        cog = RoleAdminCog(bot)
        await cog.remove.callback(cog, ctx, category="rank", key="Omniscient")

        bot.role_manager.remove_role.assert_awaited_once_with(RoleCategory.RANK, "Omniscient")
        ctx.respond.assert_awaited_once()
        assert "Removed dynamic role" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_remove_not_found(self, ctx, bot):
        """Test removing a non-existent dynamic role."""
        bot.role_manager.remove_role = AsyncMock(return_value=False)

        cog = RoleAdminCog(bot)
        await cog.remove.callback(cog, ctx, category="rank", key="NonExistent")

        ctx.respond.assert_awaited_once()
        assert "No role found" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_remove_invalid_category(self, ctx, bot):
        """Test removing with an invalid category returns an error."""
        cog = RoleAdminCog(bot)
        await cog.remove.callback(cog, ctx, category="bad_cat", key="Key")

        ctx.respond.assert_awaited_once()
        assert "Invalid category" in ctx.respond.call_args[0][0]

    # ── update command ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_update_success(self, ctx, bot):
        """Test updating an existing dynamic role."""
        bot.role_manager.update_role = AsyncMock(return_value=True)
        new_role = helpers.MockRole(id=7777, name="NewRole")

        cog = RoleAdminCog(bot)
        await cog.update.callback(cog, ctx, category="rank", key="Omniscient", role=new_role)

        bot.role_manager.update_role.assert_awaited_once_with(RoleCategory.RANK, "Omniscient", new_role.id)
        ctx.respond.assert_awaited_once()
        assert "Updated" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_not_found(self, ctx, bot):
        """Test updating a non-existent dynamic role."""
        bot.role_manager.update_role = AsyncMock(return_value=None)
        new_role = helpers.MockRole(id=7777, name="NewRole")

        cog = RoleAdminCog(bot)
        await cog.update.callback(cog, ctx, category="rank", key="NonExistent", role=new_role)

        ctx.respond.assert_awaited_once()
        assert "No role found" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_update_invalid_category(self, ctx, bot):
        """Test updating with an invalid category returns an error."""
        new_role = helpers.MockRole(id=7777, name="NewRole")

        cog = RoleAdminCog(bot)
        await cog.update.callback(cog, ctx, category="bad_cat", key="Key", role=new_role)

        ctx.respond.assert_awaited_once()
        assert "Invalid category" in ctx.respond.call_args[0][0]

    # ── list command ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_list_no_roles(self, ctx, bot):
        """Test listing when no dynamic roles are configured."""
        bot.role_manager.list_roles = AsyncMock(return_value=[])

        cog = RoleAdminCog(bot)
        await cog.list.callback(cog, ctx, category=None)

        ctx.respond.assert_awaited_once()
        assert "No dynamic roles configured" in ctx.respond.call_args[0][0]

    @pytest.mark.asyncio
    async def test_list_with_roles(self, ctx, bot):
        """Test listing dynamic roles grouped by category."""
        mock_role_entry = MagicMock()
        mock_role_entry.category = RoleCategory.RANK
        mock_role_entry.key = "Omniscient"
        mock_role_entry.discord_role_id = 1234
        mock_role_entry.display_name = "Omniscient Rank"

        guild_role = helpers.MockRole(id=1234, name="Omniscient")
        ctx.guild.get_role = MagicMock(return_value=guild_role)

        bot.role_manager.list_roles = AsyncMock(return_value=[mock_role_entry])

        cog = RoleAdminCog(bot)
        await cog.list.callback(cog, ctx, category=None)

        ctx.respond.assert_awaited_once()
        call_kwargs = ctx.respond.call_args[1]
        embed = call_kwargs["embed"]
        assert embed.title == "Dynamic Roles"
        assert len(embed.fields) == 1
        assert embed.fields[0].name == "rank"

    @pytest.mark.asyncio
    async def test_list_with_category_filter(self, ctx, bot):
        """Test listing dynamic roles filtered by a specific category."""
        bot.role_manager.list_roles = AsyncMock(return_value=[])

        cog = RoleAdminCog(bot)
        await cog.list.callback(cog, ctx, category="rank")

        bot.role_manager.list_roles.assert_awaited_once_with(RoleCategory.RANK)

    @pytest.mark.asyncio
    async def test_list_role_not_in_guild(self, ctx, bot):
        """Test listing when a role ID does not exist in the guild (shows raw ID)."""
        mock_role_entry = MagicMock()
        mock_role_entry.category = RoleCategory.RANK
        mock_role_entry.key = "Ghost"
        mock_role_entry.discord_role_id = 99999
        mock_role_entry.display_name = "Ghost Rank"

        ctx.guild.get_role = MagicMock(return_value=None)
        bot.role_manager.list_roles = AsyncMock(return_value=[mock_role_entry])

        cog = RoleAdminCog(bot)
        await cog.list.callback(cog, ctx, category=None)

        ctx.respond.assert_awaited_once()
        call_kwargs = ctx.respond.call_args[1]
        embed = call_kwargs["embed"]
        # When guild role is not found, the raw ID should be shown
        assert "99999" in embed.fields[0].value

    # ── reload command ───────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_reload(self, ctx, bot):
        """Test the reload command calls role_manager.reload."""
        bot.role_manager.reload = AsyncMock()

        cog = RoleAdminCog(bot)
        await cog.reload.callback(cog, ctx)

        bot.role_manager.reload.assert_awaited_once()
        ctx.respond.assert_awaited_once()
        assert "reloaded" in ctx.respond.call_args[0][0].lower()

    # ── setup ────────────────────────────────────────────────────────

    def test_setup(self, bot):
        """Test the setup function registers the cog."""
        role_admin.setup(bot)
        bot.add_cog.assert_called_once()
