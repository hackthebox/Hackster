import logging

from discord import Bot, Guild, Member
from discord.errors import NotFound
from fastapi import HTTPException

from src.core import settings
from src.webhooks.types import WebhookBody, WebhookEvent

logger = logging.getLogger(__name__)


async def handler(body: WebhookBody, bot: Bot) -> dict:
    """Handles incoming webhook events and performs actions accordingly."""
    guild = await bot.fetch_guild(settings.guild_ids[0])
    discord_id = int(body.data["discord_id"])

    try:
        member = await guild.fetch_member(discord_id)
    except ValueError as exc:
        logger.debug("Invalid Discord ID", exc_info=exc)
        raise HTTPException(status_code=400, detail="Invalid Discord ID") from exc
    except NotFound as exc:
        logger.debug("User is not in the Discord server", exc_info=exc)
        raise HTTPException(status_code=400, detail="User is not in the Discord server") from exc

    if body.event == WebhookEvent.ACCOUNT_LINKED:
        await handle_account_linked(body, guild, member)
    elif body.event == WebhookEvent.CERTIFICATE_AWARDED:
        await handle_certificate_awarded(body, guild, member)
    elif body.event == WebhookEvent.ACCOUNT_UNLINKED:
        await handle_account_unlinked(body, guild, member)
    else:
        logger.debug(f"Event {body.event} not implemented")
        raise HTTPException(status_code=501, detail=f"Event {body.event} not implemented")

    return {"success": True}


async def handle_account_linked(body: WebhookBody, guild: Guild, member: Member) -> None:
    """Handles account linking events."""
    roles_to_add = {settings.roles.ACADEMY_USER}
    roles_to_add.update(settings.get_academy_cert_role(cert["id"]) for cert in body.data["certifications"])

    role_ids_to_add = {role_id for role_id in roles_to_add if role_id is not None}
    roles_to_add = {guild.get_role(role_id) for role_id in role_ids_to_add}

    await member.add_roles(*roles_to_add, atomic=True)


async def handle_certificate_awarded(body: WebhookBody, member: Member) -> None:
    """Handles certificate awarding events."""
    cert_id = body.data["certification"]["id"]
    role = settings.get_academy_cert_role(cert_id)

    if not role:
        logger.debug(f"Role for certification: {cert_id} does not exist")
        raise HTTPException(status_code=400, detail=f"Role for certification: {cert_id} does not exist")

    await member.add_roles(role, atomic=True)


async def handle_account_unlinked(guild: Guild, member: Member) -> None:
    """Handles account unlinking events."""
    current_role_ids = {role.id for role in member.roles}
    cert_role_ids = {settings.get_academy_cert_role(cert_id) for _, cert_id in settings.academy_certificates}

    common_role_ids = current_role_ids.intersection(cert_role_ids)
    role_ids_to_remove = {settings.roles.ACADEMY_USER}.union(common_role_ids)
    roles_to_remove = {guild.get_role(role_id) for role_id in role_ids_to_remove}

    await member.remove_roles(*roles_to_remove, atomic=True)
