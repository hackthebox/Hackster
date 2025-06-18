import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord import Bot, Member
from discord.errors import NotFound
from fastapi import HTTPException

from src.webhooks.handlers.account import AccountHandler
from src.webhooks.types import WebhookBody, Platform, WebhookEvent
from tests import helpers


class TestAccountHandler:
    """Test the `AccountHandler` class."""

    def test_initialization(self):
        """Test that AccountHandler initializes correctly."""
        handler = AccountHandler()

        assert isinstance(handler.logger, logging.Logger)
        assert handler.logger.name == "AccountHandler"

    @pytest.mark.asyncio
    async def test_handle_account_linked_event(self, bot):
        """Test handle method routes ACCOUNT_LINKED event correctly."""
        handler = AccountHandler()
        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={"discord_id": 123456789, "account_id": 987654321},
            traits={},
        )

        with patch.object(
            handler, "handle_account_linked", new_callable=AsyncMock
        ) as mock_handle:
            await handler.handle(body, bot)
            mock_handle.assert_called_once_with(body, bot)

    @pytest.mark.asyncio
    async def test_handle_account_unlinked_event(self, bot):
        """Test handle method routes ACCOUNT_UNLINKED event correctly."""
        handler = AccountHandler()
        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_UNLINKED,
            properties={"discord_id": 123456789, "account_id": 987654321},
            traits={},
        )

        with patch.object(
            handler, "handle_account_unlinked", new_callable=AsyncMock
        ) as mock_handle:
            await handler.handle(body, bot)
            mock_handle.assert_called_once_with(body, bot)

    @pytest.mark.asyncio
    async def test_handle_account_deleted_event(self, bot):
        """Test handle method with ACCOUNT_DELETED event (method not implemented)."""
        handler = AccountHandler()
        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_DELETED,
            properties={"discord_id": 123456789, "account_id": 987654321},
            traits={},
        )

        # The handle_account_deleted method is not implemented, so this should raise AttributeError
        with pytest.raises(AttributeError):
            await handler.handle(body, bot)

    @pytest.mark.asyncio
    async def test_handle_unknown_event(self, bot):
        """Test handle method with unknown event does nothing."""
        handler = AccountHandler()
        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.CERTIFICATE_AWARDED,  # Not handled by AccountHandler
            properties={"discord_id": 123456789, "account_id": 987654321},
            traits={},
        )

        # Should not raise any exceptions, just do nothing
        await handler.handle(body, bot)

    @pytest.mark.asyncio
    async def test_handle_account_linked_success(self, bot):
        """Test successful account linking."""
        handler = AccountHandler()
        discord_id = 123456789
        account_id = 987654321
        mock_member = helpers.MockMember(id=discord_id, mention="@testuser")

        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={"discord_id": discord_id, "account_id": account_id},
            traits={"htb_user_id": 555},
        )

        # Create a custom bot mock without spec_set restrictions for this test
        custom_bot = MagicMock()
        custom_bot.send_message = AsyncMock()

        with (
            patch.object(
                handler, "validate_discord_id", return_value=discord_id
            ) as mock_validate_discord,
            patch.object(
                handler, "validate_account_id", return_value=account_id
            ) as mock_validate_account,
            patch.object(
                handler,
                "get_guild_member",
                new_callable=AsyncMock,
                return_value=mock_member,
            ) as mock_get_member,
            patch.object(
                handler,
                "merge_properties_and_traits",
                return_value={
                    "discord_id": discord_id,
                    "account_id": account_id,
                    "htb_user_id": 555,
                },
            ) as mock_merge,
            patch(
                "src.webhooks.handlers.account.process_account_identification",
                new_callable=AsyncMock,
            ) as mock_process,
            patch("src.webhooks.handlers.account.settings") as mock_settings,
            patch.object(handler.logger, "info") as mock_log,
        ):
            mock_settings.channels.VERIFY_LOGS = 12345
            
            await handler.handle_account_linked(body, custom_bot)

            # Verify all method calls
            mock_validate_discord.assert_called_once_with(discord_id)
            mock_validate_account.assert_called_once_with(account_id)
            mock_get_member.assert_called_once_with(discord_id, custom_bot)
            mock_merge.assert_called_once_with(body.properties, body.traits)
            mock_process.assert_called_once_with(
                mock_member,
                custom_bot,
                traits={
                    "discord_id": discord_id,
                    "account_id": account_id,
                    "htb_user_id": 555,
                },
            )
            custom_bot.send_message.assert_called_once_with(
                12345, f"Account linked: {account_id} -> (@testuser ({discord_id})"
            )
            mock_log.assert_called_once_with(
                f"Account {account_id} linked to {discord_id}",
                extra={"account_id": account_id, "discord_id": discord_id},
            )

    @pytest.mark.asyncio
    async def test_handle_account_linked_invalid_discord_id(self, bot):
        """Test account linking with invalid Discord ID."""
        handler = AccountHandler()

        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={"discord_id": None, "account_id": 987654321},
            traits={},
        )

        with patch.object(
            handler,
            "validate_discord_id",
            side_effect=HTTPException(status_code=400, detail="Invalid Discord ID"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await handler.handle_account_linked(body, bot)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "Invalid Discord ID"

    @pytest.mark.asyncio
    async def test_handle_account_linked_invalid_account_id(self, bot):
        """Test account linking with invalid Account ID."""
        handler = AccountHandler()

        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={"discord_id": 123456789, "account_id": None},
            traits={},
        )

        with (
            patch.object(handler, "validate_discord_id", return_value=123456789),
            patch.object(
                handler,
                "validate_account_id",
                side_effect=HTTPException(status_code=400, detail="Invalid Account ID"),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await handler.handle_account_linked(body, bot)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "Invalid Account ID"

    @pytest.mark.asyncio
    async def test_handle_account_linked_user_not_in_guild(self, bot):
        """Test account linking when user is not in the Discord guild."""
        handler = AccountHandler()
        discord_id = 123456789
        account_id = 987654321

        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={"discord_id": discord_id, "account_id": account_id},
            traits={},
        )

        with (
            patch.object(handler, "validate_discord_id", return_value=discord_id),
            patch.object(handler, "validate_account_id", return_value=account_id),
            patch.object(
                handler,
                "get_guild_member",
                new_callable=AsyncMock,
                side_effect=HTTPException(
                    status_code=400, detail="User is not in the Discord server"
                ),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await handler.handle_account_linked(body, bot)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "User is not in the Discord server"

    @pytest.mark.asyncio
    async def test_handle_account_unlinked_success(self, bot):
        """Test successful account unlinking."""
        handler = AccountHandler()
        discord_id = 123456789
        account_id = 987654321
        mock_member = helpers.MockMember(id=discord_id)

        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_UNLINKED,
            properties={"discord_id": discord_id, "account_id": account_id},
            traits={},
        )

        with (
            patch.object(
                handler, "validate_discord_id", return_value=discord_id
            ) as mock_validate_discord,
            patch.object(
                handler, "validate_account_id", return_value=account_id
            ) as mock_validate_account,
            patch.object(
                handler,
                "get_guild_member",
                new_callable=AsyncMock,
                return_value=mock_member,
            ) as mock_get_member,
            patch("src.webhooks.handlers.account.settings") as mock_settings,
        ):
            mock_settings.roles.VERIFIED = helpers.MockRole(id=99999, name="Verified")
            mock_member.remove_roles = AsyncMock()

            await handler.handle_account_unlinked(body, bot)

            # Verify all method calls
            mock_validate_discord.assert_called_once_with(discord_id)
            mock_validate_account.assert_called_once_with(account_id)
            mock_get_member.assert_called_once_with(discord_id, bot)
            mock_member.remove_roles.assert_called_once_with(
                mock_settings.roles.VERIFIED, atomic=True
            )

    @pytest.mark.asyncio
    async def test_handle_account_unlinked_invalid_discord_id(self, bot):
        """Test account unlinking with invalid Discord ID."""
        handler = AccountHandler()

        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_UNLINKED,
            properties={"discord_id": None, "account_id": 987654321},
            traits={},
        )

        with patch.object(
            handler,
            "validate_discord_id",
            side_effect=HTTPException(status_code=400, detail="Invalid Discord ID"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await handler.handle_account_unlinked(body, bot)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "Invalid Discord ID"

    @pytest.mark.asyncio
    async def test_handle_account_unlinked_invalid_account_id(self, bot):
        """Test account unlinking with invalid Account ID."""
        handler = AccountHandler()

        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_UNLINKED,
            properties={"discord_id": 123456789, "account_id": None},
            traits={},
        )

        with (
            patch.object(handler, "validate_discord_id", return_value=123456789),
            patch.object(
                handler,
                "validate_account_id",
                side_effect=HTTPException(status_code=400, detail="Invalid Account ID"),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await handler.handle_account_unlinked(body, bot)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "Invalid Account ID"

    @pytest.mark.asyncio
    async def test_handle_account_unlinked_user_not_in_guild(self, bot):
        """Test account unlinking when user is not in the Discord guild."""
        handler = AccountHandler()
        discord_id = 123456789
        account_id = 987654321

        body = WebhookBody(
            platform=Platform.ACCOUNT,
            event=WebhookEvent.ACCOUNT_UNLINKED,
            properties={"discord_id": discord_id, "account_id": account_id},
            traits={},
        )

        with (
            patch.object(handler, "validate_discord_id", return_value=discord_id),
            patch.object(handler, "validate_account_id", return_value=account_id),
            patch.object(
                handler,
                "get_guild_member",
                new_callable=AsyncMock,
                side_effect=HTTPException(
                    status_code=400, detail="User is not in the Discord server"
                ),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await handler.handle_account_unlinked(body, bot)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "User is not in the Discord server"
