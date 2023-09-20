import logging
from typing import Optional

from discord import Bot
from discord.abc import GuildChannel
from discord.errors import Forbidden
from fastapi import HTTPException

from src.core import settings
from src.webhooks.types import WebhookBody, WebhookEvent

logger = logging.getLogger(__name__)


async def handler(body: WebhookBody, bot: Bot) -> dict:
    """
    Handles incoming webhook events and performs actions accordingly.

    This function processes Pro Lab resets events sent by Midna and sends a message
    to the respective channel (#prolabs-<prolab_name>).

    Args:
        body (WebhookBody): The data received from the webhook.
        bot (Bot): The instance of the Discord bot.

    Returns:
        dict: A dictionary with a "success" key indicating whether the operation was successful.

    Raises:
        HTTPException: If an error occurs while processing the webhook event.
    """
    if body.event != WebhookEvent.PROLAB_RESET:
        raise ValueError(f"Event {body.event} not implemented")

    prolab_name_data: str = body.data.get("prolabName")

    if not prolab_name_data:
        logger.debug("Missing required data in webhook body: %s", body.data)
        raise HTTPException(
            status_code=400, detail="Missing required data in webhook body"
        )

    separator = "-"
    separator_count = prolab_name_data.count(separator)
    if separator_count != 2:
        logger.debug("Invalid prolab name data: %s", prolab_name_data)
        raise HTTPException(status_code=400, detail="Invalid prolab name data")

    prolab_name_data = prolab_name_data.lower()
    prolab_region, prolab_name, prolab_vpn_id = prolab_name_data.split(separator)

    channel_name = "prolabs-" + prolab_name.lower()
    logger.debug("Looking for channel %s", channel_name)
    prolab_channel: Optional[GuildChannel] = None

    try:
        guild = await bot.fetch_guild(settings.guild_ids[0])
    except Forbidden as forbidden:
        raise HTTPException(
            status_code=500, detail="Missing permissions to fetch guild"
        ) from forbidden
    except HTTPException as http_exc:
        raise HTTPException(
            status_code=500, detail="Failed to fetch guild"
        ) from http_exc

    channels = await guild.fetch_channels()
    for channel in channels:
        if channel.name == channel_name:
            prolab_channel = channel
            break

    if not prolab_channel:
        raise HTTPException(
            status_code=400,
            detail=f"Channel {channel_name} for prolab {prolab_name} does not exist",
        )

    prolab_name = prolab_name.upper()
    prolab_region = prolab_region.upper()
    content = (
        f"**{prolab_name}** has started to reset in **{prolab_region} {prolab_vpn_id}**"
    )
    logger.debug("Sending '%s' to channel %s", content, prolab_channel.name)

    try:
        await prolab_channel.send(content=content)
    except Forbidden as forbidden:
        raise HTTPException(
            status_code=500, detail="Missing permissions to send message"
        ) from forbidden
    except HTTPException as http_exc:
        raise HTTPException(
            status_code=500, detail="Failed to send message"
        ) from http_exc

    return {"success": True}
