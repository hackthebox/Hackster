import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException

from src.webhooks.handlers.mp import MPHandler
from src.webhooks.types import WebhookBody, Platform, WebhookEvent
from tests import helpers

class TestMPHandler:
    @pytest.mark.asyncio
    async def test_handle_invalid_event(self, bot):
        handler = MPHandler()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.CERTIFICATE_AWARDED,  # Not handled by MPHandler
            properties={},
            traits={},
        )
        with pytest.raises(ValueError, match="Invalid event"):
            await handler.handle(body, bot)

    @pytest.mark.asyncio
    async def test_handle_subscription_change_success(self, bot):
        handler = MPHandler()
        discord_id = 123456789
        account_id = 987654321
        subscription_name = "VIP"
        mock_member = helpers.MockMember(id=discord_id)
        mock_member.add_roles = AsyncMock()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.SUBSCRIPTION_CHANGE,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "subscription_name": subscription_name,
            },
            traits={},
        )
        with (
            patch.object(handler, "validate_common_properties", return_value=(discord_id, account_id)),
            patch.object(handler, "validate_property", return_value=subscription_name),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.mp.settings") as mock_settings,
        ):
            mock_settings.get_post_or_rank.return_value = 555
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.return_value = 555
            bot.guilds = [mock_guild]
            result = await handler._handle_subscription_change(body, bot)
            mock_member.add_roles.assert_awaited()
            assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_subscription_change_invalid_role(self, bot):
        handler = MPHandler()
        discord_id = 123456789
        account_id = 987654321
        subscription_name = "INVALID"
        mock_member = helpers.MockMember(id=discord_id)
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.SUBSCRIPTION_CHANGE,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "subscription_name": subscription_name,
            },
            traits={},
        )
        with (
            patch.object(handler, "validate_common_properties", return_value=(discord_id, account_id)),
            patch.object(handler, "validate_property", return_value=subscription_name),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.mp.settings") as mock_settings,
        ):
            mock_settings.get_post_or_rank.return_value = None
            with pytest.raises(ValueError, match="Invalid subscription name"):
                await handler._handle_subscription_change(body, bot)

    @pytest.mark.asyncio
    async def test_handle_hof_change_success_top1(self, bot):
        handler = MPHandler()
        discord_id = 123456789
        account_id = 987654321
        hof_tier = "1"
        mock_member = helpers.MockMember(id=discord_id)
        mock_member.roles = []
        mock_member.add_roles = AsyncMock()
        mock_member.remove_roles = AsyncMock()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.HOF_CHANGE,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "hof_tier": hof_tier,
            },
            traits={},
        )
        mock_role_1 = MagicMock()
        mock_role_10 = MagicMock()
        with (
            patch.object(handler, "validate_common_properties", return_value=(discord_id, account_id)),
            patch.object(handler, "validate_property", return_value=hof_tier),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.mp.settings") as mock_settings,
            patch.object(handler, "_find_user_with_role", new_callable=AsyncMock, return_value=None),
        ):
            mock_settings.roles.RANK_ONE = 1
            mock_settings.roles.RANK_TEN = 10
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.side_effect = lambda rid: mock_role_1 if rid == 1 else mock_role_10
            bot.guilds = [mock_guild]
            result = await handler._handle_hof_change(body, bot)
            mock_member.add_roles.assert_awaited_with(mock_role_1, atomic=True)
            assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_hof_change_invalid_tier(self, bot):
        handler = MPHandler()
        discord_id = 123456789
        account_id = 987654321
        hof_tier = "99"
        mock_member = helpers.MockMember(id=discord_id)
        mock_member.roles = []
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.HOF_CHANGE,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "hof_tier": hof_tier,
            },
            traits={},
        )
        with (
            patch.object(handler, "validate_common_properties", return_value=(discord_id, account_id)),
            patch.object(handler, "validate_property", return_value=hof_tier),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.mp.settings") as mock_settings,
        ):
            mock_settings.roles.RANK_ONE = 1
            mock_settings.roles.RANK_TEN = 10
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.side_effect = lambda rid: None
            bot.guilds = [mock_guild]
            with pytest.raises(ValueError, match="Invalid HOF tier"):
                await handler._handle_hof_change(body, bot)

    @pytest.mark.asyncio
    async def test_handle_rank_up_success(self, bot):
        handler = MPHandler()
        discord_id = 123456789
        account_id = 987654321
        rank = "Elite Hacker"
        mock_member = helpers.MockMember(id=discord_id)
        mock_member.roles = []
        mock_member.add_roles = AsyncMock()
        mock_member.remove_roles = AsyncMock()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.RANK_UP,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "rank": rank,
            },
            traits={},
        )
        mock_role = MagicMock()
        with (
            patch.object(handler, "validate_discord_id", return_value=discord_id),
            patch.object(handler, "validate_account_id", return_value=account_id),
            patch.object(handler, "validate_property", return_value=rank),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.mp.settings") as mock_settings,
        ):
            mock_settings.role_groups = {"ALL_RANKS": [555]}
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.return_value = mock_role
            bot.guilds = [mock_guild]
            result = await handler._handle_rank_up(body, bot)
            mock_member.add_roles.assert_awaited_with(mock_role, atomic=True)
            assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_rank_up_invalid_role(self, bot):
        handler = MPHandler()
        discord_id = 123456789
        account_id = 987654321
        rank = "Nonexistent"
        mock_member = helpers.MockMember(id=discord_id)
        mock_member.roles = []
        mock_member.add_roles = AsyncMock()
        mock_member.remove_roles = AsyncMock()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.RANK_UP,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "rank": rank,
            },
            traits={},
        )
        with (
            patch.object(handler, "validate_discord_id", return_value=discord_id),
            patch.object(handler, "validate_account_id", return_value=account_id),
            patch.object(handler, "validate_property", return_value=rank),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
        ):
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.return_value = None
            bot.guilds = [mock_guild]
            with pytest.raises(ValueError, match="Cannot find role for"):
                await handler._handle_rank_up(body, bot) 