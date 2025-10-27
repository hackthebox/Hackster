from discord import Bot, Member, Role

from typing import Literal

from src.core import settings
from src.webhooks.handlers.base import BaseHandler
from src.webhooks.types import WebhookBody, WebhookEvent


class MPHandler(BaseHandler):
    async def handle(self, body: WebhookBody, bot: Bot):
        """
        Handles incoming webhook events and performs actions accordingly.

        This function processes different webhook events originating from the
        HTB Account.
        """
        if body.event == WebhookEvent.HOF_CHANGE:
            return await self._handle_hof_change(body, bot)
        elif body.event == WebhookEvent.RANK_UP:
            return await self._handle_rank_up(body, bot)
        elif body.event == WebhookEvent.SUBSCRIPTION_CHANGE:
            return await self._handle_subscription_change(body, bot)
        elif body.event == WebhookEvent.SEASON_RANK_CHANGE:
            return await self._handle_season_rank(body, bot)
        else:
            raise ValueError(f"Invalid event: {body.event}")

    async def _handle_subscription_change(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the subscription change event.
        """
        discord_id, _ = self.validate_common_properties(body)
        subscription_name = self.validate_property(
            body.properties.get("subscription_name"), "subscription_name"
        )

        member = await self.get_guild_member(discord_id, bot)

        subscription_id = settings.get_post_or_rank(subscription_name)
        if not subscription_id:
            raise ValueError(f"Invalid subscription name: {subscription_name}")

        # Use the base handler's role swapping method
        role_group = [int(r) for r in settings.role_groups["ALL_LABS_SUBSCRIPTIONS"]]
        await self.swap_role_in_group(member, subscription_id, role_group, bot)

        return self.success()

    async def _handle_hof_change(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the HOF change event.
        """
        self.logger.info("Handling HOF change event.")
        discord_id, account_id = self.validate_common_properties(body)
        hof_tier: Literal["1", "10"] = self.validate_property(
            self.get_property_or_trait(body, "hof_tier"),
            "hof_tier",  # type: ignore
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

        if int(hof_tier) == 1:
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
        elif int(hof_tier) == 10:
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

    async def _handle_rank_up(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the rank up event.
        """
        discord_id, account_id = self.validate_common_properties(body)
        rank = self.validate_property(self.get_property_or_trait(body, "rank"), "rank")

        member = await self.get_guild_member(discord_id, bot)

        rank_id = settings.get_post_or_rank(rank)
        if not rank_id:
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

        # Use the base handler's role swapping method
        role_group = [int(r) for r in settings.role_groups["ALL_RANKS"]]
        changes_made = await self.swap_role_in_group(member, rank_id, role_group, bot)
        
        if not changes_made:
            return self.success()  # No changes needed

        return self.success()

    async def _handle_season_rank(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the season rank event.
        """
        discord_id, account_id = self.validate_common_properties(body)
        season_rank = self.validate_property(
            self.get_property_or_trait(body, "season_rank"), "season_rank"
        )

        season_role_id = settings.get_season(season_rank)
        if not season_role_id:
            err = ValueError(f"Cannot find role for '{season_rank}'")
            self.logger.error(
                err,
                extra={
                    "account_id": account_id,
                    "discord_id": discord_id,
                    "season_rank": season_rank,
                },
            )
            raise err

        member = await self.get_guild_member(discord_id, bot)

        # Use the base handler's role swapping method
        role_group = [int(r) for r in settings.role_groups["ALL_SEASON_RANKS"]]
        await self.swap_role_in_group(member, season_role_id, role_group, bot)

        return self.success()