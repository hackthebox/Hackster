from discord import Bot

from src.core import settings
from src.webhooks.handlers.base import BaseHandler
from src.webhooks.types import WebhookBody, WebhookEvent


class AcademyHandler(BaseHandler):
    async def handle(self, body: WebhookBody, bot: Bot):
        """
        Handles incoming webhook events and performs actions accordingly.

        This function processes different webhook events originating from the
        HTB Account.
        """
        if body.event == WebhookEvent.CERTIFICATE_AWARDED:
            return await self._handle_certificate_awarded(body, bot)
        if body.event == WebhookEvent.SUBSCRIPTION_CHANGE:
            return await self._handle_subscription_change(body, bot)
        else:
            raise ValueError(f"Invalid event: {body.event}")

    async def _handle_certificate_awarded(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the certificate awarded event.
        """
        discord_id, _ = self.validate_common_properties(body)
        certificate_id = self.validate_property(
            self.get_property_or_trait(body, "certificate_id"), "certificate_id"
        )

        self.logger.info(f"Handling certificate awarded event for {discord_id} with certificate {certificate_id}")

        member = await self.get_guild_member(discord_id, bot)
        certificate_role_id = settings.get_academy_cert_role(int(certificate_id))

        if not certificate_role_id:
            self.logger.warning(f"No certificate role found for certificate {certificate_id}")
            return self.fail()

        if certificate_role_id:
            self.logger.info(f"Adding certificate role {certificate_role_id} to member {member.id}")
            try:
                await member.add_roles(
                    bot.guilds[0].get_role(certificate_role_id), atomic=True  # type: ignore
                )  # type: ignore
            except Exception as e:
                self.logger.error(f"Error adding certificate role {certificate_role_id} to member {member.id}: {e}")
                raise e

        return self.success()

    async def _handle_subscription_change(self, body: WebhookBody, bot: Bot) -> dict:
        """
        Handles the subscription change event.
        """
        discord_id, _ = self.validate_common_properties(body)
        plan = self.validate_property(self.get_property_or_trait(body, "plan"), "plan")

        self.logger.info(f"Handling subscription change event for {discord_id} with plan {plan}")

        member = await self.get_guild_member(discord_id, bot)
        subscription_role_id = settings.get_post_or_rank(plan)
        if not subscription_role_id:
            self.logger.warning(f"No subscription role found for plan {plan}")
            return self.fail()

        # Use the base handler's role swapping method
        role_group = [int(r) for r in settings.role_groups["ALL_ACADEMY_SUBSCRIPTIONS"]]
        await self.swap_role_in_group(member, subscription_role_id, role_group, bot)

        return self.success()