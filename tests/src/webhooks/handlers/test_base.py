import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord import Bot
from discord.errors import NotFound
from fastapi import HTTPException

from src.webhooks.handlers.base import BaseHandler
from src.webhooks.types import WebhookBody, Platform, WebhookEvent
from tests import helpers


class ConcreteHandler(BaseHandler):
    """Concrete implementation of BaseHandler for testing purposes."""

    async def handle(self, body: WebhookBody, bot: Bot) -> dict:
        return {"status": "handled"}


class TestBaseHandler:
    """Test the `BaseHandler` class."""

    def test_initialization(self):
        """Test that BaseHandler initializes correctly."""
        handler = ConcreteHandler()

        assert isinstance(handler.logger, logging.Logger)
        assert handler.logger.name == "ConcreteHandler"

    def test_constants(self):
        """Test that all required constants are defined."""
        handler = ConcreteHandler()

        assert handler.ACADEMY_USER_ID == "academy_user_id"
        assert handler.MP_USER_ID == "mp_user_id"
        assert handler.EP_USER_ID == "ep_user_id"
        assert handler.CTF_USER_ID == "ctf_user_id"
        assert handler.ACCOUNT_ID == "account_id"
        assert handler.DISCORD_ID == "discord_id"

    @pytest.mark.asyncio
    async def test_get_guild_member_success(self, bot):
        """Test successful guild member retrieval."""
        handler = ConcreteHandler()
        discord_id = 123456789
        mock_guild = helpers.MockGuild(id=12345)
        mock_member = helpers.MockMember(id=discord_id)

        bot.fetch_guild = AsyncMock(return_value=mock_guild)
        mock_guild.fetch_member = AsyncMock(return_value=mock_member)

        with patch("src.webhooks.handlers.base.settings") as mock_settings:
            mock_settings.guild_ids = [12345]

            result = await handler.get_guild_member(discord_id, bot)

            assert result == mock_member
            bot.fetch_guild.assert_called_once_with(12345)
            mock_guild.fetch_member.assert_called_once_with(discord_id)

    @pytest.mark.asyncio
    async def test_get_guild_member_not_found(self, bot):
        """Test guild member retrieval when user is not in server."""
        handler = ConcreteHandler()
        discord_id = 123456789
        mock_guild = helpers.MockGuild(id=12345)

        bot.fetch_guild = AsyncMock(return_value=mock_guild)
        mock_guild.fetch_member = AsyncMock(
            side_effect=NotFound(MagicMock(), "User not found")
        )

        with patch("src.webhooks.handlers.base.settings") as mock_settings:
            mock_settings.guild_ids = [12345]

            with pytest.raises(HTTPException) as exc_info:
                await handler.get_guild_member(discord_id, bot)

            assert exc_info.value.status_code == 400
            assert exc_info.value.detail == "User is not in the Discord server"

    def test_validate_property_success(self):
        """Test successful property validation."""
        handler = ConcreteHandler()

        result = handler.validate_property("valid_value", "test_property")
        assert result == "valid_value"

        result = handler.validate_property(123, "test_number")
        assert result == 123

    def test_validate_property_none(self):
        """Test property validation with None value."""
        handler = ConcreteHandler()

        with pytest.raises(HTTPException) as exc_info:
            handler.validate_property(None, "test_property")

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid test_property"

    def test_validate_discord_id_success(self):
        """Test successful Discord ID validation."""
        handler = ConcreteHandler()

        result = handler.validate_discord_id(123456789)
        assert result == 123456789

        result = handler.validate_discord_id("987654321")
        assert result == "987654321"

    def test_validate_discord_id_none(self):
        """Test Discord ID validation with None value."""
        handler = ConcreteHandler()

        with pytest.raises(HTTPException) as exc_info:
            handler.validate_discord_id(None)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid Discord ID"

    def test_validate_account_id_success(self):
        """Test successful Account ID validation."""
        handler = ConcreteHandler()

        result = handler.validate_account_id(123456789)
        assert result == 123456789

        result = handler.validate_account_id("987654321")
        assert result == "987654321"

    def test_validate_account_id_none(self):
        """Test Account ID validation with None value."""
        handler = ConcreteHandler()

        with pytest.raises(HTTPException) as exc_info:
            handler.validate_account_id(None)

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid Account ID"

    def test_get_property_or_trait_from_properties(self):
        """Test getting value from properties."""
        handler = ConcreteHandler()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={"test_key": 123},
            traits={"test_key": 456, "other_key": 789},
        )

        result = handler.get_property_or_trait(body, "test_key")
        assert result == 123  # Should prioritize properties over traits

    def test_get_property_or_trait_from_traits(self):
        """Test getting value from traits when not in properties."""
        handler = ConcreteHandler()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={},
            traits={"test_key": 456},
        )

        result = handler.get_property_or_trait(body, "test_key")
        assert result == 456

    def test_get_property_or_trait_not_found(self):
        """Test getting value when key is not found."""
        handler = ConcreteHandler()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={},
            traits={},
        )

        result = handler.get_property_or_trait(body, "missing_key")
        assert result is None

    def test_merge_properties_and_traits_no_duplicates(self):
        """Test merging properties and traits without duplicates."""
        handler = ConcreteHandler()
        properties = {"key1": 1, "key2": 2}
        traits = {"key3": 3, "key4": 4}

        result = handler.merge_properties_and_traits(properties, traits)

        expected = {"key1": 1, "key2": 2, "key3": 3, "key4": 4}
        assert result == expected

    def test_merge_properties_and_traits_with_duplicates(self):
        """Test merging properties and traits with duplicate keys."""
        handler = ConcreteHandler()
        properties = {"key1": 1, "key2": 2}
        traits = {"key2": 99, "key3": 3}  # key2 is duplicate

        result = handler.merge_properties_and_traits(properties, traits)

        expected = {"key1": 1, "key2": 2, "key3": 3}  # Properties value should win
        assert result == expected

    def test_merge_properties_and_traits_empty_properties(self):
        """Test merging when properties is empty."""
        handler = ConcreteHandler()
        properties = {}
        traits = {"key1": 1, "key2": 2}

        result = handler.merge_properties_and_traits(properties, traits)

        assert result == traits

    def test_merge_properties_and_traits_empty_traits(self):
        """Test merging when traits is empty."""
        handler = ConcreteHandler()
        properties = {"key1": 1, "key2": 2}
        traits = {}

        result = handler.merge_properties_and_traits(properties, traits)

        assert result == properties

    def test_get_platform_properties_all_present(self):
        """Test getting platform properties when all are present."""
        handler = ConcreteHandler()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={
                "account_id": 1,
                "mp_user_id": 2,
                "ep_user_id": 3,
                "ctf_user_id": 4,
                "academy_user_id": 5,
            },
            traits={},
        )

        result = handler.get_platform_properties(body)

        expected = {
            "account_id": 1,
            "mp_user_id": 2,
            "ep_user_id": 3,
            "ctf_user_id": 4,
            "academy_user_id": 5,
        }
        assert result == expected

    def test_get_platform_properties_mixed_sources(self):
        """Test getting platform properties from both properties and traits."""
        handler = ConcreteHandler()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={"account_id": 1, "mp_user_id": 2},
            traits={"ep_user_id": 3, "ctf_user_id": 4, "academy_user_id": 5},
        )

        result = handler.get_platform_properties(body)

        expected = {
            "account_id": 1,
            "mp_user_id": 2,
            "ep_user_id": 3,
            "ctf_user_id": 4,
            "academy_user_id": 5,
        }
        assert result == expected

    def test_get_platform_properties_missing_values(self):
        """Test getting platform properties when some are missing."""
        handler = ConcreteHandler()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={"account_id": 1},
            traits={"mp_user_id": 2},
        )

        result = handler.get_platform_properties(body)

        expected = {
            "account_id": 1,
            "mp_user_id": 2,
            "ep_user_id": None,
            "ctf_user_id": None,
            "academy_user_id": None,
        }
        assert result == expected

    def test_get_platform_properties_properties_override_traits(self):
        """Test that properties override traits for the same key."""
        handler = ConcreteHandler()
        body = WebhookBody(
            platform=Platform.MAIN,
            event=WebhookEvent.ACCOUNT_LINKED,
            properties={"account_id": 1, "mp_user_id": 2},
            traits={
                "mp_user_id": 999,  # Should be overridden
                "ep_user_id": 3,
            },
        )

        result = handler.get_platform_properties(body)

        expected = {
            "account_id": 1,
            "mp_user_id": 2,  # Properties value should win
            "ep_user_id": 3,
            "ctf_user_id": None,
            "academy_user_id": None,
        }
        assert result == expected
