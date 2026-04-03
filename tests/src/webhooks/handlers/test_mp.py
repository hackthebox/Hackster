import pytest
from unittest.mock import AsyncMock, MagicMock

from src.webhooks.handlers.mp import MPHandler
from src.webhooks.types import WebhookBody, Platform, WebhookEvent
from tests import helpers


def _make_role_manager(**overrides):
    """Create a MockRoleManager with optional method overrides."""
    rm = helpers.MockRoleManager()
    for attr, val in overrides.items():
        setattr(rm, attr, val if callable(val) else lambda *a, v=val, **kw: v)
    return rm


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
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=subscription_name)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(
            get_post_or_rank=lambda what: 555,
            get_group_ids=lambda cat: [555, 666, 777],
        )
        mock_role = MagicMock()
        mock_role.id = 555
        mock_guild = helpers.MockGuild(id=1)
        mock_guild.get_role.return_value = mock_role
        bot.guilds = [mock_guild]

        result = await handler._handle_subscription_change(body, bot)
        mock_member.add_roles.assert_awaited_once()
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
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=subscription_name)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(get_post_or_rank=lambda what: None)
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
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=hof_tier)
        handler.get_guild_member = AsyncMock(return_value=mock_member)
        handler._find_user_with_role = AsyncMock(return_value=None)

        bot.role_manager = _make_role_manager(
            get_role_id=lambda cat, key: 1 if key == "1" else (10 if key == "10" else None),
        )
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
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=hof_tier)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(
            get_role_id=lambda cat, key: None,
        )
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
        mock_role.id = 555
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=rank)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(
            get_post_or_rank=lambda what: 555,
            get_group_ids=lambda cat: [555, 666, 777],
        )
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
        handler.validate_common_properties = MagicMock(return_value=(discord_id, account_id))
        handler.validate_property = MagicMock(return_value=rank)
        handler.get_guild_member = AsyncMock(return_value=mock_member)

        bot.role_manager = _make_role_manager(get_post_or_rank=lambda what: None)
        mock_guild = helpers.MockGuild(id=1)
        mock_guild.get_role.return_value = None
        bot.guilds = [mock_guild]

        with pytest.raises(ValueError, match="Cannot find role for"):
            await handler._handle_rank_up(body, bot)
