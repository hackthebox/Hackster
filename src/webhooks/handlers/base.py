import logging

from abc import ABC, abstractmethod
from typing import TypeVar

from discord import Bot, Member
from discord.errors import NotFound
from fastapi import HTTPException

from src.core import settings
from src.webhooks.types import WebhookBody

T = TypeVar("T")


class BaseHandler(ABC):
    ACADEMY_USER_ID = "academy_user_id"
    MP_USER_ID = "mp_user_id"
    EP_USER_ID = "ep_user_id"
    CTF_USER_ID = "ctf_user_id" 
    ACCOUNT_ID = "account_id"
    DISCORD_ID = "discord_id"


    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    async def handle(self, body: WebhookBody, bot: Bot) -> dict:
        pass

    async def get_guild_member(self, discord_id: int, bot: Bot) -> Member:
        """
        Fetches a guild member from the Discord server.

        Args:
            discord_id (int): The Discord ID of the user.
            bot (Bot): The Discord bot instance.

        Returns:
            Member: The guild member.

        Raises:
            HTTPException: If the user is not in the Discord server (400)
        """
        try:
            guild = await bot.fetch_guild(settings.guild_ids[0])
            member = await guild.fetch_member(discord_id)
            return member

        except NotFound as exc:
            self.logger.debug("User is not in the Discord server", exc_info=exc)
            raise HTTPException(
                status_code=400, detail="User is not in the Discord server"
            ) from exc

    def validate_property(self, property: T | None, name: str) -> T:
        """
        Validates a property is not None.

        Args:
            property (T | None): The property to validate.
            name (str): The name of the property.

        Returns:
            T: The validated property.

        Raises:
            HTTPException: If the property is None (400)
        """
        if property is None:
            msg = f"Invalid {name}"
            self.logger.debug(msg)
            raise HTTPException(status_code=400, detail=msg)

        return property

    def validate_discord_id(self, discord_id: str | int) -> int:
        """
        Validates the Discord ID. See validate_property function.
        """
        return self.validate_property(discord_id, "Discord ID")

    def validate_account_id(self, account_id: str | int) -> int:
        """
        Validates the Account ID. See validate_property function.
        """
        return self.validate_property(account_id, "Account ID")

    def get_property_or_trait(self, body: WebhookBody, name: str) -> int | None:
        """
        Gets a trait or property from the webhook body.
        """
        return body.properties.get(name) or body.traits.get(name)
    
    def merge_properties_and_traits(self, properties: dict[str, int | None], traits: dict[str, int | None]) -> dict[str, int | None]:
        """
        Merges the properties and traits from the webhook body without duplicates.
        If a property and trait have the same name but different values, the property value will be used.
        """
        return {**properties, **{k: v for k, v in traits.items() if k not in properties}}

    def get_platform_properties(self, body: WebhookBody) -> dict[str, int | None]:
        """
        Gets the platform properties from the webhook body.
        """
        properties = {
            self.ACCOUNT_ID: self.get_property_or_trait(body, self.ACCOUNT_ID),
            self.MP_USER_ID: self.get_property_or_trait(body, self.MP_USER_ID),
            self.EP_USER_ID: self.get_property_or_trait(body, self.EP_USER_ID),
            self.CTF_USER_ID: self.get_property_or_trait(body, self.CTF_USER_ID),
            self.ACADEMY_USER_ID: self.get_property_or_trait(body, self.ACADEMY_USER_ID),
        }
        return properties