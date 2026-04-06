"""Tests for Admin cog."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.cmds.core import admin
from src.database.models.dynamic_role import DynamicRole, RoleCategory
from tests import helpers


class TestAdminCog:
    """Test the Admin cog."""

    @pytest.mark.asyncio
    async def test_add_role_success(self, ctx, bot):
        """Test adding a dynamic role."""
        mock_role = MagicMock()
        mock_role.id = 123456789
        mock_role.mention = "<@&123456789>"

        bot.role_manager = MagicMock()
        bot.role_manager.add_role = AsyncMock()

        cog = admin.AdminCog(bot)
        await cog.add.callback(
            cog, ctx, "rank", "TestRole", mock_role, "Test Display Name",
            None, None, None  # description, cert_full_name, cert_integer_id
        )

        bot.role_manager.add_role.assert_called_once_with(
            key="TestRole",
            category=RoleCategory.RANK,
            discord_role_id=123456789,
            display_name="Test Display Name",
            description=None,
            cert_full_name=None,
            cert_integer_id=None,
        )
        ctx.respond.assert_called_once_with(
            "Added dynamic role: `rank/TestRole` -> <@&123456789>",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_add_role_with_cert(self, ctx, bot):
        """Test adding a cert role with extra fields."""
        mock_role = MagicMock()
        mock_role.id = 123456789
        mock_role.mention = "<@&123456789>"

        bot.role_manager = MagicMock()
        bot.role_manager.add_role = AsyncMock()

        cog = admin.AdminCog(bot)
        await cog.add.callback(
            cog,
            ctx,
            "academy_cert",
            "CPTS",
            mock_role,
            "CPTS Cert",
            None,  # description
            "HTB Certified Penetration Testing Specialist",
            3,
        )

        bot.role_manager.add_role.assert_called_once_with(
            key="CPTS",
            category=RoleCategory.ACADEMY_CERT,
            discord_role_id=123456789,
            display_name="CPTS Cert",
            description=None,
            cert_full_name="HTB Certified Penetration Testing Specialist",
            cert_integer_id=3,
        )

    @pytest.mark.asyncio
    async def test_add_role_invalid_category(self, ctx, bot):
        """Test adding a role with invalid category."""
        mock_role = MagicMock()

        cog = admin.AdminCog(bot)
        await cog.add.callback(
            cog, ctx, "invalid_category", "TestRole", mock_role, "Test",
            None, None, None  # description, cert_full_name, cert_integer_id
        )

        ctx.respond.assert_called_once_with(
            "Invalid category: invalid_category",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_remove_role_success(self, ctx, bot):
        """Test removing a dynamic role successfully."""
        bot.role_manager = MagicMock()
        bot.role_manager.remove_role = AsyncMock(return_value=True)

        cog = admin.AdminCog(bot)
        await cog.remove.callback(cog, ctx, "rank", "Omniscient")

        bot.role_manager.remove_role.assert_called_once_with(
            RoleCategory.RANK,
            "Omniscient",
        )
        ctx.respond.assert_called_once_with(
            "Removed dynamic role: `rank/Omniscient`",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_remove_role_not_found(self, ctx, bot):
        """Test removing a role that doesn't exist."""
        bot.role_manager = MagicMock()
        bot.role_manager.remove_role = AsyncMock(return_value=False)

        cog = admin.AdminCog(bot)
        await cog.remove.callback(cog, ctx, "rank", "NonExistent")

        ctx.respond.assert_called_once_with(
            "No role found for `rank/NonExistent`",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_update_role_success(self, ctx, bot):
        """Test updating a dynamic role successfully."""
        mock_role = MagicMock()
        mock_role.id = 987654321
        mock_role.mention = "<@&987654321>"

        bot.role_manager = MagicMock()
        bot.role_manager.update_role = AsyncMock(return_value=True)

        cog = admin.AdminCog(bot)
        await cog.update.callback(cog, ctx, "rank", "Omniscient", mock_role)

        bot.role_manager.update_role.assert_called_once_with(
            RoleCategory.RANK,
            "Omniscient",
            987654321,
        )
        ctx.respond.assert_called_once_with(
            "Updated `rank/Omniscient` -> <@&987654321>",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_update_role_not_found(self, ctx, bot):
        """Test updating a role that doesn't exist."""
        mock_role = MagicMock()
        mock_role.id = 987654321

        bot.role_manager = MagicMock()
        bot.role_manager.update_role = AsyncMock(return_value=False)

        cog = admin.AdminCog(bot)
        await cog.update.callback(cog, ctx, "rank", "NonExistent", mock_role)

        ctx.respond.assert_called_once_with(
            "No role found for `rank/NonExistent`",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_list_roles_empty(self, ctx, bot):
        """Test listing roles when none are configured."""
        bot.role_manager = MagicMock()
        bot.role_manager.list_roles = AsyncMock(return_value=[])

        cog = admin.AdminCog(bot)
        await cog.list.callback(cog, ctx, None)

        ctx.respond.assert_called_once_with(
            "No dynamic roles configured.",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_list_roles_with_data(self, ctx, bot, guild):
        """Test listing roles with data."""
        ctx.guild = guild

        mock_roles = [
            DynamicRole(
                id=1,
                key="Omniscient",
                discord_role_id=586528519459438592,
                category=RoleCategory.RANK,
                display_name="Omniscient",
            ),
            DynamicRole(
                id=2,
                key="Hacker",
                discord_role_id=586528079363702801,
                category=RoleCategory.RANK,
                display_name="Hacker",
            ),
        ]

        bot.role_manager = MagicMock()
        bot.role_manager.list_roles = AsyncMock(return_value=mock_roles)

        cog = admin.AdminCog(bot)
        await cog.list.callback(cog, ctx, None)

        # Should respond with an embed
        assert ctx.respond.called
        call_args = ctx.respond.call_args
        assert call_args.kwargs.get("ephemeral") is True
        assert "embed" in call_args.kwargs

    @pytest.mark.asyncio
    async def test_reload_success(self, ctx, bot):
        """Test reloading dynamic roles."""
        bot.role_manager = MagicMock()
        bot.role_manager.reload = AsyncMock()

        cog = admin.AdminCog(bot)
        await cog.reload.callback(cog, ctx)

        bot.role_manager.reload.assert_called_once()
        ctx.respond.assert_called_once_with(
            "Dynamic roles reloaded from database.",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_remove_role_invalid_category(self, ctx, bot):
        """Test removing with an invalid category returns an error."""
        cog = admin.AdminCog(bot)
        await cog.remove.callback(cog, ctx, "bad_cat", "Key")

        ctx.respond.assert_called_once_with(
            "Invalid category: bad_cat",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_update_role_invalid_category(self, ctx, bot):
        """Test updating with an invalid category returns an error."""
        mock_role = helpers.MockRole(id=7777, name="NewRole")

        cog = admin.AdminCog(bot)
        await cog.update.callback(cog, ctx, "bad_cat", "Key", mock_role)

        ctx.respond.assert_called_once_with(
            "Invalid category: bad_cat",
            ephemeral=True,
        )

    @pytest.mark.asyncio
    async def test_list_roles_with_category_filter(self, ctx, bot):
        """Test listing dynamic roles filtered by a specific category."""
        bot.role_manager = MagicMock()
        bot.role_manager.list_roles = AsyncMock(return_value=[])

        cog = admin.AdminCog(bot)
        await cog.list.callback(cog, ctx, "rank")

        bot.role_manager.list_roles.assert_called_once_with(RoleCategory.RANK)

    @pytest.mark.asyncio
    async def test_list_role_not_in_guild(self, ctx, bot):
        """Test listing when a role ID does not exist in the guild (shows raw ID)."""
        mock_role_entry = MagicMock()
        mock_role_entry.category = RoleCategory.RANK
        mock_role_entry.key = "Ghost"
        mock_role_entry.discord_role_id = 99999
        mock_role_entry.display_name = "Ghost Rank"

        ctx.guild.get_role = MagicMock(return_value=None)
        bot.role_manager = MagicMock()
        bot.role_manager.list_roles = AsyncMock(return_value=[mock_role_entry])

        cog = admin.AdminCog(bot)
        await cog.list.callback(cog, ctx, None)

        ctx.respond.assert_called_once()
        call_args = ctx.respond.call_args
        assert call_args.kwargs.get("ephemeral") is True
        embed = call_args.kwargs["embed"]
        # When guild role is not found, the raw ID should be shown
        assert "99999" in embed.fields[0].value

    def test_setup(self, bot):
        """Test the setup function registers the cog."""
        admin.setup(bot)
        bot.add_cog.assert_called_once()
