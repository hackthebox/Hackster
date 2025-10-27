import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.webhooks.handlers.academy import AcademyHandler
from src.webhooks.types import WebhookBody, Platform, WebhookEvent
from tests import helpers

class TestAcademyHandler:
    @pytest.mark.asyncio
    async def test_handle_certificate_awarded_success(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        certificate_id = 42
        mock_member = helpers.MockMember(id=discord_id)
        mock_member.add_roles = AsyncMock()
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.CERTIFICATE_AWARDED,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "certificate_id": certificate_id,
            },
            traits={},
        )
        with (
            patch.object(handler, "validate_common_properties", return_value=(discord_id, account_id)),
            patch.object(handler, "validate_property", return_value=certificate_id),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.academy.settings") as mock_settings,
            patch.object(handler.logger, "info") as mock_log,
        ):
            mock_settings.get_academy_cert_role.return_value = 555
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.return_value = 555
            bot.guilds = [mock_guild]
            result = await handler._handle_certificate_awarded(body, bot)
            mock_member.add_roles.assert_awaited()
            mock_log.assert_called()
            assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_certificate_awarded_no_role(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        certificate_id = 42
        mock_member = helpers.MockMember(id=discord_id)
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.CERTIFICATE_AWARDED,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "certificate_id": certificate_id,
            },
            traits={},
        )
        with (
            patch.object(handler, "validate_common_properties", return_value=(discord_id, account_id)),
            patch.object(handler, "validate_property", return_value=certificate_id),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.academy.settings") as mock_settings,
            patch.object(handler.logger, "warning") as mock_log,
        ):
            mock_settings.get_academy_cert_role.return_value = None
            result = await handler._handle_certificate_awarded(body, bot)
            mock_log.assert_called()
            assert result == handler.fail()

    @pytest.mark.asyncio
    async def test_handle_certificate_awarded_add_roles_error(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        certificate_id = 42
        mock_member = helpers.MockMember(id=discord_id)
        mock_member.add_roles = AsyncMock(side_effect=Exception("add_roles error"))
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.CERTIFICATE_AWARDED,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "certificate_id": certificate_id,
            },
            traits={},
        )
        with (
            patch.object(handler, "validate_common_properties", return_value=(discord_id, account_id)),
            patch.object(handler, "validate_property", return_value=certificate_id),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.academy.settings") as mock_settings,
            patch.object(handler.logger, "error") as mock_log,
        ):
            mock_settings.get_academy_cert_role.return_value = 555
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.return_value = 555
            bot.guilds = [mock_guild]
            with pytest.raises(Exception, match="add_roles error"):
                await handler._handle_certificate_awarded(body, bot)
            mock_log.assert_called()

    @pytest.mark.asyncio
    async def test_handle_subscription_change_success(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        plan = "Silver Annual"
        mock_member = helpers.MockMember(id=discord_id)
        mock_member.roles = []
        mock_member.add_roles = AsyncMock()
        mock_member.remove_roles = AsyncMock()
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.SUBSCRIPTION_CHANGE,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "plan": plan,
            },
            traits={},
        )
        mock_role = MagicMock()
        mock_role.id = 555
        with (
            patch.object(handler, "validate_common_properties", return_value=(discord_id, account_id)),
            patch.object(handler, "validate_property", return_value=plan),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.academy.settings") as mock_settings,
            patch.object(handler.logger, "info") as mock_log,
        ):
            mock_settings.get_post_or_rank.return_value = 555
            mock_settings.role_groups = {"ALL_ACADEMY_SUBSCRIPTIONS": [555, 666, 777]}
            mock_guild = helpers.MockGuild(id=1)
            mock_guild.get_role.return_value = mock_role
            bot.guilds = [mock_guild]
            result = await handler._handle_subscription_change(body, bot)
            mock_member.add_roles.assert_awaited_once()
            mock_log.assert_called()
            assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_subscription_change_no_role(self, bot):
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        plan = "invalid_plan"
        mock_member = helpers.MockMember(id=discord_id)
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.SUBSCRIPTION_CHANGE,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "plan": plan,
            },
            traits={},
        )
        with (
            patch.object(handler, "validate_common_properties", return_value=(discord_id, account_id)),
            patch.object(handler, "validate_property", return_value=plan),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.academy.settings") as mock_settings,
            patch.object(handler.logger, "warning") as mock_log,
        ):
            mock_settings.get_post_or_rank.return_value = None
            result = await handler._handle_subscription_change(body, bot)
            mock_log.assert_called()
            assert result == handler.fail()

    @pytest.mark.asyncio
    async def test_handle_subscription_change_role_swap(self, bot):
        """Test that subscription change properly swaps roles"""
        handler = AcademyHandler()
        discord_id = 123456789
        account_id = 987654321
        plan = "professional"
        
        # Mock member with an existing academy subscription role
        old_role = MagicMock()
        old_role.id = 666
        mock_member = helpers.MockMember(id=discord_id)
        mock_member.roles = [old_role]
        mock_member.add_roles = AsyncMock()
        mock_member.remove_roles = AsyncMock()
        
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.SUBSCRIPTION_CHANGE,
            properties={
                "discord_id": discord_id,
                "account_id": account_id,
                "plan": plan,
            },
            traits={},
        )
        
        new_role = MagicMock()
        new_role.id = 555
        
        with (
            patch.object(handler, "validate_common_properties", return_value=(discord_id, account_id)),
            patch.object(handler, "validate_property", return_value=plan),
            patch.object(handler, "get_guild_member", new_callable=AsyncMock, return_value=mock_member),
            patch("src.webhooks.handlers.academy.settings") as mock_settings,
        ):
            mock_settings.get_post_or_rank.return_value = 555
            mock_settings.role_groups = {"ALL_ACADEMY_SUBSCRIPTIONS": [555, 666, 777]}
            mock_guild = helpers.MockGuild(id=1)
            
            def get_role_mock(role_id):
                if role_id == 555:
                    return new_role
                elif role_id == 666:
                    return old_role
                return None
            
            mock_guild.get_role.side_effect = get_role_mock
            bot.guilds = [mock_guild]
            
            result = await handler._handle_subscription_change(body, bot)
            
            # Verify old role was removed and new role was added
            mock_member.remove_roles.assert_awaited_once_with(old_role, atomic=True)
            mock_member.add_roles.assert_awaited_once_with(new_role, atomic=True)
            assert result == handler.success()

    @pytest.mark.asyncio
    async def test_handle_invalid_event(self, bot):
        handler = AcademyHandler()
        body = WebhookBody(
            platform=Platform.ACADEMY,
            event=WebhookEvent.RANK_UP,  # Not handled by AcademyHandler
            properties={},
            traits={},
        )
        with pytest.raises(ValueError, match="Invalid event"):
            await handler.handle(body, bot) 