from discord import Bot

from src.core import settings
from src.helpers.verification import process_account_identification
from src.webhooks.types import WebhookBody, WebhookEvent

from src.webhooks.handlers.base import BaseHandler



class AccountHandler(BaseHandler):
    async def handle(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles incoming webhook events and performs actions accordingly.

        This function processes different webhook events originating from the
        HTB Account.
        """
        if body.event == WebhookEvent.ACCOUNT_LINKED:
            await self.handle_account_linked(body, bot)
        elif body.event == WebhookEvent.ACCOUNT_UNLINKED:
            await self.handle_account_unlinked(body, bot)
        elif body.event == WebhookEvent.ACCOUNT_DELETED:
            await self.handle_account_deleted(body, bot)

    async def handle_account_linked(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the account linked event.
        """
        discord_id = self.validate_discord_id(body.properties.get("discord_id"))
        account_id = self.validate_account_id(body.properties.get("account_id"))

        member = await self.get_guild_member(discord_id, bot)
        await process_account_identification(member, bot, traits=self.merge_properties_and_traits(body.properties, body.traits))
        await bot.send_message(settings.channels.VERIFY_LOGS, f"Account linked: {account_id} -> ({member.mention} ({member.id})")

        self.logger.info(f"Account {account_id} linked to {member.id}", extra={"account_id": account_id, "discord_id": discord_id})

    async def handle_account_unlinked(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the account unlinked event.
        """
        discord_id = self.validate_discord_id(body.properties.get("discord_id"))
        account_id = self.validate_account_id(body.properties.get("account_id"))

        member = await self.get_guild_member(discord_id, bot)
        
        await member.remove_roles(settings.roles.VERIFIED, atomic=True)
