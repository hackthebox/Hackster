"""Send Discord feedback to the feedback service ingest API."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from src.core import settings

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """Return True when feedback service URL and API key are both set."""
    return bool(settings.FEEDBACK_SERVICE_URL and settings.FEEDBACK_SERVICE_API_KEY)


async def ingest_discord_feedback(payload: dict[str, Any]) -> bool:
    """POST a payload to the feedback service /api/ingest/discord endpoint.

    Returns True when the service accepts the payload (HTTP 202).
    """
    if not is_configured():
        return False

    headers = {"Authorization": f"Bearer {settings.FEEDBACK_SERVICE_API_KEY}"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                settings.FEEDBACK_SERVICE_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status == 202:
                    return True
                body = await response.text()
                logger.error(
                    "Feedback service ingest failed: %s - %s",
                    response.status,
                    body[:500],
                )
                return False
        except Exception:
            logger.exception("Feedback service ingest request failed")
            return False
