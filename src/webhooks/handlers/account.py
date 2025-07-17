from datetime import datetime
from discord import Bot

from src.core import settings
from src.helpers.ban import handle_platform_ban_or_update
from src.helpers.verification import process_account_identification
from src.webhooks.handlers.base import BaseHandler
from src.webhooks.types import WebhookBody, WebhookEvent


class AccountHandler(BaseHandler):
    async def handle(self, body: WebhookBody, bot: Bot):
        """
        Handles incoming webhook events and performs actions accordingly.

        This function processes different webhook events originating from the
        HTB Account.
        """
        if body.event == WebhookEvent.ACCOUNT_LINKED:
            return await self.handle_account_linked(body, bot)
        elif body.event == WebhookEvent.ACCOUNT_UNLINKED:
            return await self.handle_account_unlinked(body, bot)
        elif body.event == WebhookEvent.ACCOUNT_DELETED:
            return await self.handle_account_deleted(body, bot)
        elif body.event == WebhookEvent.ACCOUNT_BANNED:
            return await self.handle_account_banned(body, bot)
        else:
            raise ValueError(f"Invalid event: {body.event}")

    async def handle_account_linked(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the account linked event.
        """
        discord_id = self.validate_discord_id(
            self.get_property_or_trait(body, "discord_id")
        )
        account_id = self.validate_account_id(
            self.get_property_or_trait(body, "account_id")
        )

        member = await self.get_guild_member(discord_id, bot)
        await process_account_identification(
            member,
            bot,  # type: ignore
            traits=self.merge_properties_and_traits(body.properties, body.traits),
        )

        # Safely attempt to send verification log
        try:
            verify_channel = bot.guilds[0].get_channel(settings.channels.VERIFY_LOGS)
            if verify_channel:
                await verify_channel.send(  # type: ignore
                    f"Account linked: {account_id} -> ({member.mention} ({member.id})",
                )
            else:
                self.logger.warning(
                    f"Verify logs channel {settings.channels.VERIFY_LOGS} not found"
                )
        except Exception as e:
            self.logger.error(f"Failed to send verification log: {e}")
            # Don't raise - this is not critical

        self.logger.info(
            f"Account {account_id} linked to {member.id}",
            extra={"account_id": account_id, "discord_id": discord_id},
        )

        return self.success()

    async def handle_account_unlinked(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the account unlinked event.
        """
        discord_id = self.validate_discord_id(
            self.get_property_or_trait(body, "discord_id")
        )
        account_id = self.validate_account_id(
            self.get_property_or_trait(body, "account_id")
        )

        member = await self.get_guild_member(discord_id, bot)

        await member.remove_roles(
            bot.guilds[0].get_role(settings.roles.VERIFIED), atomic=True  # type: ignore
        )  # type: ignore

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

    async def handle_account_banned(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the account banned event.
        """
        discord_id = self.validate_discord_id(
            self.get_property_or_trait(body, "discord_id")
        )
        account_id = self.validate_account_id(
            self.get_property_or_trait(body, "account_id")
        )
        expires_at = self.validate_property(
            self.get_property_or_trait(body, "expires_at"), "expires_at"
        )
        reason = body.properties.get("reason")
        notes = body.properties.get("notes")
        created_by = body.properties.get("created_by")

        expires_ts = int(datetime.fromisoformat(expires_at).timestamp())  # type: ignore
        extra = {"account_id": account_id, "discord_id": discord_id}

        member = await self.get_guild_member(discord_id, bot)
        if not member:
            self.logger.warning(
                f"Cannot ban user {discord_id}- not found in guild", extra=extra
            )
            return self.fail()

        # Use the generic ban helper to handle all the complex logic
        result = await handle_platform_ban_or_update(
            bot=bot,  # type: ignore
            guild=bot.guilds[0],
            member=member,
            expires_timestamp=expires_ts,
            reason=f"Platform Ban - {reason}",
            evidence=notes or "N/A",
            author_name=created_by or "System",
            expires_at_str=expires_at,  # type: ignore
            log_channel_id=settings.channels.BOT_LOGS,
            logger=self.logger,
            extra_log_data=extra,
        )

        self.logger.debug(
            f"Platform ban handling result: {result['action']}", extra=extra
        )

        return self.success()

    async def handle_account_deleted(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the account deleted event.
        """
        discord_id = self.validate_discord_id(body.properties.get("discord_id"))
        account_id = self.validate_account_id(body.properties.get("account_id"))

        member = await self.get_guild_member(discord_id, bot)
        if not member:
            self.logger.warning(
                f"Cannot delete account {account_id}- not found in guild",
                extra={"account_id": account_id, "discord_id": discord_id},
            )
            return self.fail()

        await member.remove_roles(
            bot.guilds[0].get_role(settings.roles.VERIFIED), atomic=True  # type: ignore
        )  # type: ignore

        return self.success()
