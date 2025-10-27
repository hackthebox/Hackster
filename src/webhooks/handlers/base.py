import logging
from abc import ABC, abstractmethod
from typing import TypeVar

from discord import Bot, Member, Role
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

    async def get_guild_member(self, discord_id: int | str, bot: Bot) -> Member:
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
            member = await guild.fetch_member(int(discord_id))
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

    def validate_discord_id(self, discord_id: str | int | None) -> int | str:
        """
        Validates the Discord ID. See validate_property function.
        """
        return self.validate_property(discord_id, "Discord ID")

    def validate_account_id(self, account_id: str | int | None) -> int | str:
        """
        Validates the Account ID. See validate_property function.
        """
        return self.validate_property(account_id, "Account ID")

    def get_property_or_trait(self, body: WebhookBody, name: str) -> int | None:
        """
        Gets a trait or property from the webhook body.
        """
        return body.properties.get(name) or body.traits.get(name)

    def merge_properties_and_traits(
        self, properties: dict[str, int | None], traits: dict[str, int | None]
    ) -> dict[str, int | None]:
        """
        Merges the properties and traits from the webhook body without duplicates.
        If a property and trait have the same name but different values, the property value will be used.
        """
        return {
            **properties,
            **{k: v for k, v in traits.items() if k not in properties},
        }

    def get_platform_properties(self, body: WebhookBody) -> dict[str, int | None]:
        """
        Gets the platform properties from the webhook body.
        """
        properties = {
            self.ACCOUNT_ID: self.get_property_or_trait(body, self.ACCOUNT_ID),
            self.MP_USER_ID: self.get_property_or_trait(body, self.MP_USER_ID),
            self.EP_USER_ID: self.get_property_or_trait(body, self.EP_USER_ID),
            self.CTF_USER_ID: self.get_property_or_trait(body, self.CTF_USER_ID),
            self.ACADEMY_USER_ID: self.get_property_or_trait(
                body, self.ACADEMY_USER_ID
            ),
        }
        return properties

    async def swap_role_in_group(
        self,
        member: Member,
        new_role_id: int | None,
        role_group: list[int],
        bot: Bot,
        allow_no_role: bool = False,
    ) -> bool:
        """
        Swaps a member's role within a specific role group.

        This method removes any existing role from the specified group and adds the new role.

        Args:
            member: The Discord member to modify
            new_role_id: ID of the new role to assign (None to remove all roles from group)
            role_group: List of role IDs that are mutually exclusive
            bot: The Discord bot instance
            allow_no_role: If True, allows removing all roles without adding a new one

        Returns:
            bool: True if changes were made, False if no changes needed

        Raises:
            ValueError: If new_role_id is invalid or not in the role group
        """
        # Get all roles from the group as Discord Role objects
        group_roles = [
            bot.guilds[0].get_role(role_id)
            for role_id in role_group
            if bot.guilds[0].get_role(role_id)
        ]

        # Find current role from this group that the member has
        current_role = next(
            (role for role in member.roles if role in group_roles), None
        )

        # Get the new role object if specified
        new_role = None
        if new_role_id:
            new_role = bot.guilds[0].get_role(new_role_id)
            if not new_role:
                raise ValueError(f"Invalid role ID: {new_role_id}")

            # Verify the new role is in the allowed group
            if new_role not in group_roles:
                raise ValueError(
                    f"Role {new_role_id} is not in the specified role group"
                )

        # If no change needed, return early
        if current_role == new_role:
            return False

        # If we're trying to remove all roles but it's not allowed
        if not new_role and not allow_no_role and current_role:
            raise ValueError(
                "Cannot remove role without replacement when allow_no_role=False"
            )

        # Remove current role if it exists
        if current_role:
            await member.remove_roles(current_role, atomic=True)

        # Add new role if specified
        if new_role:
            await member.add_roles(new_role, atomic=True)

        return True

    def validate_common_properties(
        self, body: WebhookBody
    ) -> tuple[int | str, int | str]:
        """
        Validates and returns the common discord_id and account_id properties.

        Args:
            body: The webhook body containing properties/traits

        Returns:
            tuple: (discord_id, account_id)

        Raises:
            HTTPException: If either property is missing or invalid
        """
        discord_id = self.validate_discord_id(
            self.get_property_or_trait(body, "discord_id")
        )
        account_id = self.validate_account_id(
            self.get_property_or_trait(body, "account_id")
        )
        return discord_id, account_id

    async def _find_user_with_role(self, bot: Bot, role: Role | None) -> Member | None:
        """
        Finds the user with the given role.
        """
        if not role:
            return None

        return next((m for m in role.members), None)

    @staticmethod
    def success():
        return {"success": True}

    @staticmethod
    def fail():
        return {"success": False}
