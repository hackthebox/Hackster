import discord

from datetime import datetime
from discord import Bot, Member, Role

from typing import Literal
from sqlalchemy import select

from src.core import settings
from src.webhooks.handlers.base import BaseHandler
from src.webhooks.types import WebhookBody, WebhookEvent


class AccountHandler(BaseHandler):
    async def handle(self, body: WebhookBody, bot: Bot):
        """
        Handles incoming webhook events and performs actions accordingly.

        This function processes different webhook events originating from the
        HTB Account.
        """
        if body.event == WebhookEvent.NAME_CHANGE:
            return await self.name_change(body, bot)
        elif body.event == WebhookEvent.HOF_CHANGE:
            return await self.handle_hof_change(body, bot)
        elif body.event == WebhookEvent.RANK_UP:
            return await self.handle_rank_up(body, bot)
        elif body.event == WebhookEvent.SUBSCRIPTION_CHANGE:
            return await self.handle_subscription_change(body, bot)
        elif body.event == WebhookEvent.CERTIFICATE_AWARDED:
            return await self.handle_certificate_awarded(body, bot)
        else:
            raise ValueError(f"Invalid event: {body.event}")

    async def handle_certificate_awarded(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the certificate awarded event.
        """
        discord_id = self.validate_discord_id(body.properties.get("discord_id"))
        _ = self.validate_account_id(body.properties.get("account_id"))
        certificate_id = self.validate_property(body.properties.get("certificate_id"), "certificate_id")

        member = await self.get_guild_member(discord_id, bot)
        certificate_role_id = settings.get_academy_cert_role(int(certificate_id))

        if certificate_role_id:
            await member.add_roles(bot.guilds[0].get_role(certificate_role_id), atomic=True)  # type: ignore

        return self.success()

    async def handle_subscription_change(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the subscription change event.
        """
        discord_id = self.validate_discord_id(body.properties.get("discord_id"))
        _ = self.validate_account_id(body.properties.get("account_id"))
        subscription_name = self.validate_property(
            body.properties.get("subscription_name"), "subscription_name"
        )

        member = await self.get_guild_member(discord_id, bot)

        role = settings.get_post_or_rank(subscription_name)
        if not role:
            raise ValueError(f"Invalid subscription name: {subscription_name}")

        await member.add_roles(bot.guilds[0].get_role(role), atomic=True)  # type: ignore
        return self.success()

    async def name_change(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the name change event.
        """
        discord_id = self.validate_discord_id(body.properties.get("discord_id"))
        _ = self.validate_account_id(body.properties.get("account_id"))
        name = self.validate_property(body.properties.get("name"), "name")

        member = await self.get_guild_member(discord_id, bot)
        await member.edit(nick=name)
        return self.success()

    async def handle_hof_change(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the HOF change event.
        """
        discord_id = self.validate_discord_id(body.properties.get("discord_id"))
        account_id = self.validate_account_id(body.properties.get("account_id"))
        hof_tier: Literal["1", "10"] = self.validate_property(
            body.properties.get("hof_tier"), "hof_tier"
        )
        hof_roles = {
            "1": bot.guilds[0].get_role(settings.roles.RANK_ONE),
            "10": bot.guilds[0].get_role(settings.roles.RANK_TEN),
        }

        member = await self.get_guild_member(discord_id, bot)
        member_roles = member.roles

        if not member:
            msg = f"Cannot find member {discord_id}"
            self.logger.warning(
                msg, extra={"account_id": account_id, "discord_id": discord_id}
            )
            raise ValueError(msg)

        async def _swap_hof_roles(member: Member, role_to_grant: Role | None):
            """Grants a HOF role to a member and removes the other HOF role"""
            if not role_to_grant:
                return

            member_hof_role = next(
                (r for r in member_roles if r in hof_roles.values()), None
            )
            if member_hof_role:
                await member.remove_roles(member_hof_role, atomic=True)
            await member.add_roles(role_to_grant, atomic=True)

        if hof_tier == "1":
            # Find existing top 1 user and make them a top 10
            if existing_top_one_user := await self._find_user_with_role(
                bot, hof_roles["1"]
            ):
                if existing_top_one_user.id != member.id:
                    await _swap_hof_roles(existing_top_one_user, hof_roles["10"])
                else:
                    return self.success()

            # Grant top 1 role to member
            await _swap_hof_roles(member, hof_roles["1"])
            return self.success()

        # Just grant top 10 role to member
        elif hof_tier == "10":
            await _swap_hof_roles(member, hof_roles["10"])
            return self.success()

        else:
            err = ValueError(f"Invalid HOF tier: {hof_tier}")
            self.logger.error(
                err,
                extra={
                    "account_id": account_id,
                    "discord_id": discord_id,
                    "hof_tier": hof_tier,
                },
            )
            raise err

    async def handle_rank_up(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the rank up event.
        """
        discord_id = self.validate_discord_id(body.properties.get("discord_id"))
        account_id = self.validate_account_id(body.properties.get("account_id"))
        rank = self.validate_property(body.properties.get("rank"), "rank")

        member = await self.get_guild_member(discord_id, bot)

        rank_roles = [
            bot.guilds[0].get_role(int(r)) for r in settings.role_groups["ALL_RANKS"]
        ]  # All rank roles
        new_role = next(
            (r for r in rank_roles if r and r.name == rank), None
        )  # Get passed rank as role from rank roles
        old_role = next(
            (r for r in member.roles if r in rank_roles), None
        )  # Find existing rank role on user

        if old_role:
            await member.remove_roles(old_role, atomic=True)  # Yeet the old role

        if new_role:
            await member.add_roles(new_role, atomic=True)  # Add the new role

        if not new_role:
            # Why are you passing me BS roles?
            err = ValueError(f"Cannot find role for '{rank}'")
            self.logger.error(
                err,
                extra={
                    "account_id": account_id,
                    "discord_id": discord_id,
                    "rank": rank,
                },
            )
            raise err

        return self.success()

    async def _find_user_with_role(self, bot: Bot, role: Role | None) -> Member | None:
        """
        Finds the user with the given role.
        """
        if not role:
            return None

        return next((m for m in role.members), None)
