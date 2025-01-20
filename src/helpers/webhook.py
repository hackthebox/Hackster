"""Helper methods to handle webhook calls."""
import logging

import aiohttp

logger = logging.getLogger(__name__)


async def webhook_call(url: str, data: dict) -> None:
    """Send a POST request to the webhook URL with the given data."""
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=data) as response:
                if response.status != 200:
                    logger.error(f"Failed to send to webhook: {response.status} - {await response.text()}")
        except Exception as e:
            logger.error(f"Failed to send to webhook: {e}")
