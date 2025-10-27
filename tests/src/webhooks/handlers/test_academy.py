import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

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
            patch.object(handler, "validate_discord_id", return_value=discord_id),
            patch.object(handler, "validate_account_id", return_value=account_id),
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