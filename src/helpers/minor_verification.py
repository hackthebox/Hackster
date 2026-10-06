"""Helpers for minor flagging and parental consent verification."""

import asyncio
import logging
import time
from datetime import datetime, timezone

import aiohttp
from dateutil.relativedelta import relativedelta
from discord import Forbidden, Guild, HTTPException, Member
from sqlalchemy import select

from src.core import settings
from src.database.models import HtbDiscordLink, MinorReport, MinorReviewReviewer
from src.database.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Cache for reviewer IDs (TTL 60s) to avoid DB hit on every button interaction.
_reviewer_ids_cache: tuple[int, ...] | None = None
_reviewer_ids_cache_ts: float = 0
REVIEWER_CACHE_TTL_SEC = 60

PENDING = "pending"
APPROVED = "approved"
DENIED = "denied"
CONSENT_VERIFIED = "consent_verified"
AGED_OUT = "aged_out"


async def check_parental_consent(discord_user_id: int) -> bool:
    """
    Check if parental consent exists for a Discord user via the Nexus API.

    POST to NEXUS_API_BASE_URL/discord/user_lookup/parental_consent_exists with
    {"discord_id": "<snowflake>"} and a Bearer token. Returns True iff the
    response body contains {"exists": true}. Any error is treated as no consent.
    """
    base_url = settings.NEXUS_API_BASE_URL or ""
    if not base_url:
        logger.warning("NEXUS_API_BASE_URL not set; consent check skipped.")
        return False

    token = settings.NEXUS_API_TOKEN or ""
    if not token:
        logger.warning("NEXUS_API_TOKEN not set; consent check skipped.")
        return False

    endpoint = f"{base_url.rstrip('/')}/discord/user_lookup/parental_consent_exists"
    payload = {"discord_id": str(discord_user_id)}

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                endpoint,
                json=payload,
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.debug(
                        "Nexus consent check discord_id=%s status=%s",
                        discord_user_id,
                        resp.status,
                    )
                    return False
                try:
                    data = await resp.json(content_type=None)
                except (ValueError, TypeError, aiohttp.ContentTypeError):
                    logger.warning(
                        "Nexus consent check returned non-JSON body for discord_id=%s",
                        discord_user_id,
                    )
                    return False
                exists = bool(data.get("exists"))
                logger.debug(
                    "Nexus consent check discord_id=%s status=%s exists=%s",
                    discord_user_id,
                    resp.status,
                    exists,
                )
                return exists
    except aiohttp.ClientError as e:
        logger.warning("Nexus consent check request failed: %s", e)
        return False
    except asyncio.TimeoutError as e:
        logger.warning("Nexus consent check timed out: %s", e)
        return False


async def assign_minor_role(member: Member, guild: Guild) -> bool:
    """Assign the discrete minor role to the member. Returns True if added."""
    role_id = settings.roles.VERIFIED_MINOR
    if not role_id:
        return False
    role = guild.get_role(role_id)
    if not role:
        return False
    if role in member.roles:
        return False
    try:
        await member.add_roles(role, atomic=True)
        return True
    except (Forbidden, HTTPException) as e:
        logger.warning("Failed to assign minor role to %s: %s", member.id, e)
        return False


async def get_htb_user_id_for_discord(discord_user_id: int) -> int | None:
    """Get HTB user ID for a Discord user from HtbDiscordLink."""
    async with AsyncSessionLocal() as session:
        stmt = select(HtbDiscordLink).filter(
            HtbDiscordLink.discord_user_id == discord_user_id
        ).limit(1)
        result = await session.scalars(stmt)
        link = result.first()
        if link:
            return int(link.htb_user_id)
        return None


async def get_active_minor_report(user_id: int) -> MinorReport | None:
    """Get an active (pending) minor report for the user, if any."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(MinorReport)
            .filter(MinorReport.user_id == user_id, MinorReport.status == PENDING)
            .limit(1)
        )
        result = await session.scalars(stmt)
        return result.first()


def calculate_ban_duration(suspected_age: int) -> int:
    """
    Return Unix epoch timestamp when ban should end (user turns 18).

    suspected_age must be 1-17. Ban duration is (18 - suspected_age) years from now.
    """
    if suspected_age < 1 or suspected_age > 17:
        raise ValueError("suspected_age must be between 1 and 17")
    now = datetime.now(timezone.utc)
    years_until_18 = 18 - suspected_age
    end = now + relativedelta(years=years_until_18)
    return int(end.timestamp())


def years_until_18(suspected_age: int) -> int:
    """Return number of years until user turns 18."""
    if suspected_age < 1 or suspected_age > 17:
        raise ValueError("suspected_age must be between 1 and 17")
    return 18 - suspected_age


async def get_minor_review_reviewer_ids() -> tuple[int, ...]:
    """Return Discord user IDs of users allowed to review minor reports (from DB)."""
    global _reviewer_ids_cache, _reviewer_ids_cache_ts
    now = time.monotonic()
    if _reviewer_ids_cache is not None and (now - _reviewer_ids_cache_ts) < REVIEWER_CACHE_TTL_SEC:
        return _reviewer_ids_cache
    async with AsyncSessionLocal() as session:
        stmt = select(MinorReviewReviewer.user_id)
        result = await session.scalars(stmt)
        _reviewer_ids_cache = tuple(int(uid) for uid in result.all())
        _reviewer_ids_cache_ts = now
        return _reviewer_ids_cache


async def is_minor_review_moderator(user_id: int) -> bool:
    """Return True if the user is allowed to review minor reports (from DB)."""
    reviewer_ids = await get_minor_review_reviewer_ids()
    return user_id in reviewer_ids


def invalidate_reviewer_ids_cache() -> None:
    """Clear the reviewer IDs cache so the next check reads from the DB."""
    global _reviewer_ids_cache
    _reviewer_ids_cache = None


async def mark_report_aged_out(report_id: int) -> None:
    """Mark a consent-verified report as aged out after minor-role cleanup."""
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as session:
        report = await session.get(MinorReport, report_id)
        if report and report.status == CONSENT_VERIFIED:
            report.status = AGED_OUT
            report.updated_at = now
            await session.commit()