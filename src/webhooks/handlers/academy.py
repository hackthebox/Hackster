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
