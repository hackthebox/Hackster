import logging
from typing import Optional

from discord import Bot, Embed
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
    allowed_events = [WebhookEvent.PROLAB_RESET, WebhookEvent.PROLAB_MACHINE_RESET]
    if body.event not in allowed_events:
        logger.debug("Invalid webhook event: %s", body.event)
        raise HTTPException(status_code=400, detail="Invalid webhook event")

    prolab_name_data: str = body.data.get("prolabName")
    prolab_machine: Optional[str] = None

    if body.event == WebhookEvent.PROLAB_MACHINE_RESET:
        prolab_machine = body.data.get("prolabMachine")

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
    prolab_vpn_server = prolab_region.upper() + " " + prolab_vpn_id
    prolab_machine = prolab_machine.upper() if prolab_machine else None

    embed = Embed(title="", color=0xB98700)
    embed.add_field(name="Pro Lab", value=prolab_name, inline=False)
    if prolab_machine and body.event == WebhookEvent.PROLAB_MACHINE_RESET:
        embed.add_field(name="Machine", value=prolab_machine, inline=False)
    embed.add_field(name="VPN Server", value=prolab_vpn_server, inline=False)
    embed.set_footer(text="The reset takes a few minutes to complete. Please be patient.")

    logger.debug("Sending message to channel %s", prolab_channel.name)
    try:
        await prolab_channel.send(embed=embed, content="A Pro Lab reset has been initiated.")
    except Forbidden as forbidden:
        raise HTTPException(
            status_code=500, detail="Missing permissions to send message"
        ) from forbidden
    except HTTPException as http_exc:
        raise HTTPException(
            status_code=500, detail="Failed to send message"
        ) from http_exc

    return {"success": True}
