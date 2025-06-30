"""Helper methods to handle bans, mutes and infractions. Bot or message responses are NOT allowed."""

import asyncio
import logging
from datetime import datetime, timezone
from enum import Enum

import discord
from discord import (
    Forbidden,
    Guild,
    HTTPException,
    Member,
    NotFound,
    User,
    GuildChannel,
    TextChannel,
)
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from src.bot import Bot
from src.core import settings
from src.database.models import Ban, Infraction, Mute
from src.database.session import AsyncSessionLocal
from src.helpers.checks import member_is_staff
from src.helpers.duration import validate_duration
from src.helpers.responses import SimpleResponse
from src.helpers.schedule import schedule
from src.views.bandecisionview import BanDecisionView

logger = logging.getLogger(__name__)


class BanCodes(Enum):
    SUCCESS = "SUCCESS"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    FAILED = "FAILED"


async def _check_member(
    bot: Bot, guild: Guild, member: Member | User, author: Member = None
) -> SimpleResponse | None:
    if isinstance(member, Member):
        if member_is_staff(member):
            return SimpleResponse(
                message="You cannot ban another staff member.", delete_after=None
            )
    elif isinstance(member, User):
        member = await bot.get_member_or_user(guild, member.id)
    if member.bot:
        return SimpleResponse(
            message="You cannot ban a bot.", delete_after=None, code=BanCodes.FAILED
        )
    if author and author.id == member.id:
        return SimpleResponse(
            message="You cannot ban yourself.", delete_after=None, code=BanCodes.FAILED
        )


async def get_ban(member: Member) -> Ban | None:
    async with AsyncSessionLocal() as session:
        stmt = (
            select(Ban)
            .filter(Ban.user_id == member.id, Ban.unbanned.is_(False))
            .limit(1)
        )
        result = await session.scalars(stmt)
        return result.first()


async def update_ban(ban: Ban) -> None:
    logger.info(f"Updating ban {ban.id} for user {ban.user_id} with expiration {ban.unban_time}")
    async with AsyncSessionLocal() as session:
        session.add(ban)
        await session.commit()


async def _get_ban_or_create(
    member: Member, ban: Ban, infraction: Infraction
) -> tuple[int, bool]:
    existing_ban = await get_ban(member)
    if existing_ban:
        return existing_ban.id, True

    async with AsyncSessionLocal() as session:
        session.add(ban)
        session.add(infraction)
        await session.commit()

    ban_id: int = ban.id
    assert ban_id is not None
    return ban_id, False


async def _create_ban_response(
    member: Member | User, end_date: str, dm_banned_member: bool, needs_approval: bool
) -> SimpleResponse:
    """Create a SimpleResponse for ban operations."""
    if needs_approval:
        if member:
            message = f"{member.display_name} ({member.id}) has been banned until {end_date} (UTC)."
        else:
            message = f"{member.id} has been banned until {end_date} (UTC)."
    else:
        if member:
            message = f"Member {member.display_name} has been banned permanently."
        else:
            message = f"Member {member.id} has been banned permanently."

    if not dm_banned_member:
        message += "\n Could not DM banned member due to permission error."

    return SimpleResponse(
        message=message,
        delete_after=0 if not needs_approval else None,
        code=BanCodes.SUCCESS,
    )


async def _send_ban_notice(
    guild: Guild,
    member: Member,
    reason: str,
    author: str,
    end_date: str,
    channel: TextChannel | None,
) -> None:
    """Send a ban log to the moderator channel."""
    if not isinstance(channel, TextChannel):
        channel = guild.get_channel(settings.channels.SR_MOD)

    embed = discord.Embed(
        title="Ban",
        description=f"User {member.mention} ({member.id}) was banned on the platform and thus banned here.",
        color=0xFF2429,
    )
    embed.add_field(name="Reason", value=reason)
    embed.add_field(name="Author", value=author)
    embed.add_field(name="End Date", value=end_date)

    await channel.send(embed=embed)


async def handle_platform_ban_or_update(
    bot: Bot,
    guild: Guild,
    member: Member,
    expires_timestamp: int,
    reason: str,
    evidence: str,
    author_name: str,
    expires_at_str: str,
    log_channel_id: int,
    logger,
    extra_log_data: dict = None,
) -> dict:
    """Handle platform ban by either creating new ban, updating existing ban, or taking no action.
    
    Args:
        bot: The Discord bot instance
        guild: The guild to ban the member from
        member: The member to ban
        expires_timestamp: Unix timestamp when the ban should end
        reason: Reason for the ban
        evidence: Evidence supporting the ban (notes)
        author_name: Name of the person who created the ban
        expires_at_str: Human-readable expiration date string
        log_channel_id: Channel ID for logging ban actions
        logger: Logger instance for recording events
        extra_log_data: Additional data to include in log entries
        
    Returns:
        dict with 'action' key indicating what was done: 'unbanned', 'extended', 'no_action', 'updated', 'created'
    """
    if extra_log_data is None:
        extra_log_data = {}
    
    expires_dt = datetime.fromtimestamp(expires_timestamp)
    
    existing_ban = await get_ban(member)
    if not existing_ban:
        # No existing ban, create new one
        await ban_member_with_epoch(
            bot, guild, member, expires_timestamp, reason, evidence, needs_approval=False
        )
        await _send_ban_notice(
            guild, member, reason, author_name, expires_at_str, guild.get_channel(log_channel_id)
        )
        logger.info(f"Created new platform ban for user {member.id} until {expires_at_str}", extra=extra_log_data)
        return {"action": "created"}
    
    # Existing ban found - determine what to do based on ban type and timing
    is_platform_ban = existing_ban.reason.startswith("Platform Ban")
    
    if is_platform_ban:
        # Platform bans have authority over other platform bans
        if expires_dt < datetime.now():
            # Platform ban has expired, unban the user
            await unban_member(guild, member)
            msg = f"User {member.mention} ({member.id}) has been unbanned due to platform ban expiration."
            await guild.get_channel(log_channel_id).send(msg)
            logger.info(msg, extra=extra_log_data)
            return {"action": "unbanned"}
        
        if existing_ban.unban_time < expires_timestamp:
            # Extend the existing platform ban
            existing_ban.unban_time = expires_timestamp
            await update_ban(existing_ban)
            msg = f"User {member.mention} ({member.id}) has had their ban extended to {expires_at_str}."
            await guild.get_channel(log_channel_id).send(msg)
            logger.info(msg, extra=extra_log_data)
            return {"action": "extended"}
    else:
        # Non-platform ban exists
        if existing_ban.unban_time >= expires_timestamp:
            # Existing ban is longer than platform ban, no action needed
            logger.info(
                f"User {member.mention} ({member.id}) is already banned until {existing_ban.unban_time}, "
                f"which exceeds or equals the platform ban expiration date {expires_at_str}. No action taken.",
                extra=extra_log_data,
            )
            return {"action": "no_action"}
        else:
            # Platform ban is longer, update the existing ban
            existing_ban.unban_time = expires_timestamp
            existing_ban.reason = f"Platform Ban: {reason}"  # Update reason to indicate platform authority
            await update_ban(existing_ban)
            logger.info(f"Updated existing ban for user {member.id} until {expires_at_str}.", extra=extra_log_data)
            return {"action": "updated"}
    
    # Default case (shouldn't reach here, but for safety)
    logger.warning(f"Unexpected case in platform ban handling for user {member.id}", extra=extra_log_data)
    return {"action": "no_action"}


async def ban_member_with_epoch(
    bot: Bot,
    guild: Guild,
    member: Member | User,
    unban_epoch_time: int,
    reason: str,
    evidence: str,
    author: Member = None,
    needs_approval: bool = True,
) -> SimpleResponse | None:
    """Ban a member from the guild until a specific epoch time.
    
    Args:
        bot: The Discord bot instance
        guild: The guild to ban the member from
        member: The member or user to ban
        unban_epoch_time: Unix timestamp when the ban should end
        reason: Reason for the ban
        evidence: Evidence supporting the ban
        author: The member issuing the ban (defaults to bot user)
        needs_approval: Whether the ban requires approval
        
    Returns:
        SimpleResponse with the result of the ban operation, or None if no response needed
    """
    if checked := await _check_member(bot, guild, member, author):
        return checked

    # Validate reason
    if len(reason) == 0:
        reason = "No reason given ..."

    if not evidence:
        evidence = "none provided"

    # Validate epoch time is in the future
    current_time = datetime.now(tz=timezone.utc).timestamp()
    if unban_epoch_time <= current_time:
        return SimpleResponse(
            message="Unban time must be in the future",
            delete_after=15
        )

    end_date: str = datetime.fromtimestamp(unban_epoch_time, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    if author is None:
        author = bot.user

    ban = Ban(
        user_id=member.id,
        reason=reason,
        moderator_id=author.id,
        unban_time=unban_epoch_time,
        approved=False if needs_approval else True,
    )
    infraction = Infraction(
        user_id=member.id,
        reason=f"Previously banned for: {reason} - Evidence: {evidence}",
        weight=0,
        moderator_id=author.id,
        date=datetime.now().date(),
    )
    ban_id, is_existing = await _get_ban_or_create(member, ban, infraction)
    if is_existing:
        return SimpleResponse(
            message=f"A ban with id: {ban_id} already exists for member {member}",
            delete_after=None,
            code=BanCodes.ALREADY_EXISTS,
        )

    # DM member, before we ban, else we cannot dm since we do not share a guild
    dm_banned_member = await _dm_banned_member(end_date, guild, member, reason)
    # Try to actually ban the member from the guild
    try:
        await guild.ban(member, reason=reason, delete_message_seconds=0)
    except Forbidden as exc:
        logger.warning(
            "Ban failed due to permission error",
            exc_info=exc,
            extra={"ban_requestor": author.name, "ban_receiver": member.id},
        )
        if author:
            return SimpleResponse(
                message="You do not have the proper permissions to ban.",
                delete_after=None,
                code=BanCodes.FAILED,
            )
        return
    except HTTPException as ex:
        logger.warning(
            f"HTTPException when trying to ban user with ID {member.id}", exc_info=ex
        )
        if author:
            return SimpleResponse(
                message="Here's a 400 Bad Request for you. Just like when you tried to ask me out, last week.",
                delete_after=None,
                code=BanCodes.FAILED,
            )
        return

    # If approval is required, send a message to the moderator channel about the ban
    if not needs_approval:
        logger.info(
            "Member has been banned permanently.",
            extra={
                "ban_requestor": author.name,
                "ban_receiver": member.id,
                "dm_banned_member": dm_banned_member,
            },
        )

        unban_task = schedule(
            unban_member(guild, member), run_at=datetime.fromtimestamp(ban.unban_time)
        )
        asyncio.create_task(unban_task)
        logger.debug(
            "Unbanned sceduled for ban",
            extra={"ban_id": ban_id, "unban_time": ban.unban_time},
        )
    else:
        member_name = f"{member.display_name} ({member.name})"
        embed = discord.Embed(
            title=f"Ban request #{ban_id}",
            description=f"{author.display_name} ({author.name}) "
            f"would like to ban {member_name} until {end_date} (UTC).\n"
            f"Reason: {reason}\n"
            f"Evidence: {evidence}",
        )
        embed.set_thumbnail(url=f"{settings.HTB_URL}/images/logo600.png")
        view = BanDecisionView(ban_id, bot, guild, member, end_date, reason)
        await guild.get_channel(settings.channels.SR_MOD).send(embed=embed, view=view)

    return await _create_ban_response(
        member, end_date, dm_banned_member, needs_approval
    )


async def ban_member(
    bot: Bot,
    guild: Guild,
    member: Member | User,
    duration: str | int,
    reason: str,
    evidence: str,
    author: Member = None,
    needs_approval: bool = True,
) -> SimpleResponse | None:
    """Ban a member from the guild using a duration.
    
    Args:
        bot: The Discord bot instance
        guild: The guild to ban the member from
        member: The member or user to ban
        duration: Duration string (e.g., "1d", "1h") or seconds as int
        reason: Reason for the ban
        evidence: Evidence supporting the ban
        author: The member issuing the ban (defaults to bot user)
        needs_approval: Whether the ban requires approval
        
    Returns:
        SimpleResponse with the result of the ban operation, or None if no response needed
    """
    dur, dur_exc = validate_duration(duration)

    # Check if duration is valid,
    # negative values are generally not allowed,
    # so they should be caught here
    if dur <= 0:
        return SimpleResponse(message=dur_exc, delete_after=15)

    return await ban_member_with_epoch(
        bot=bot,
        guild=guild,
        member=member,
        unban_epoch_time=dur,
        reason=reason,
        evidence=evidence,
        author=author,
        needs_approval=needs_approval,
    )


async def _dm_banned_member(
    end_date: str, guild: Guild, member: Member, reason: str
) -> bool:
    """Send a message to the member about the ban."""
    message = (
        f"You have been banned from {guild.name} until {end_date} (UTC). "
        f"To appeal the ban, please reach out to an Administrator.\n"
        f"Following is the reason given:\n>>> {reason}\n"
    )
    try:
        await member.send(message)
        return True
    except Forbidden as ex:
        logger.warning(
            f"Could not DM member with id {member.id} due to privacy settings, however will still attempt to ban "
            f"them...",
            exc_info=ex,
        )
    except HTTPException as ex:
        logger.warning(
            f"HTTPException when trying to unban user with ID {member.id}", exc_info=ex
        )
    return False


async def unban_member(guild: Guild, member: Member) -> Member:
    """Unban a member from the guild."""
    try:
        await guild.unban(member)
        logger.info(f"Unbanned user {member.id}.")
    except Forbidden as ex:
        logger.error(
            f"Permission denied when trying to unban user with ID {member.id}",
            exc_info=ex,
        )
    except NotFound as ex:
        logger.error(
            f"NotFound when trying to unban user with ID {member.id}. "
            f"This could indicate that the user is not currently banned.",
            exc_info=ex,
        )
    except HTTPException as ex:
        logger.error(
            f"HTTPException when trying to unban user with ID {member.id}", exc_info=ex
        )

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Ban)
            .filter(Ban.user_id == member.id)
            .filter(Ban.unbanned.is_(False))
            .limit(1)
        )
        result = await session.scalars(stmt)
        ban = result.first()
        if ban:
            ban.unbanned = True
            await session.commit()
        else:
            raise NoResultFound(f"Ban not found for user ID {member.id}")

    logger.debug(f"Set unbanned to True for user_id: {member.id}")
    return member


async def mute_member(
    bot: Bot,
    guild: Guild,
    member: Member,
    duration: str,
    reason: str,
    author: Member = None,
) -> SimpleResponse | None:
    """Mute a member on the guild."""
    if checked := await _check_member(bot, guild, member, author):
        return checked

    # Validate reason
    if len(reason) == 0:
        reason = "No reason given ..."

    # Validate duration
    dur, dur_exc = validate_duration(duration)
    # Check if duration is valid, negative values are generally not allowed, so they should be caught here
    if dur <= 0:
        return SimpleResponse(message=dur_exc, delete_after=15)

    if author is None:
        author = bot.user

    role = guild.get_role(settings.roles.MUTED)

    if member:
        # No longer on the server - cleanup, but don't attempt to remove a role
        logger.info(f"Add mute from {member.name}:{member.id}.")
        await member.add_roles(role, reason=reason)

        mute = Mute(
            user_id=member.id, reason=reason, moderator_id=author.id, unmute_time=dur
        )
        async with AsyncSessionLocal() as session:
            session.add(mute)
            await session.commit()


async def unmute_member(guild: Guild, member: Member) -> Member:
    """Unmute a member from the guild."""
    role = guild.get_role(settings.roles.MUTED)

    if isinstance(member, Member):
        # No longer on the server - cleanup, but don't attempt to remove a role
        logger.info(f"Remove mute from {member.name}:{member.id}.")
        await member.remove_roles(role)
        await member.remove_timeout()

    async with AsyncSessionLocal() as session:
        stmt = select(Mute).filter(Mute.user_id == member.id)
        result = await session.scalars(stmt)
        mute = result.first()
        if mute:
            await session.delete(mute)
            await session.commit()
        else:
            raise NoResultFound(f"Mute not found for user ID {member.id}")

    logger.debug(f"Mute removed for user_id: {member.id}")
    return member


async def add_infraction(
    guild: Guild, member: Member, weight: int, reason: str, author: Member
) -> SimpleResponse:
    """Add an infraction record in DB."""
    if len(reason) == 0:
        reason = "No reason given ..."

    infraction = Infraction(
        user_id=member.id, reason=reason, weight=weight, moderator_id=author.id
    )
    async with AsyncSessionLocal() as session:
        session.add(infraction)
        await session.commit()

    message = f"{member.mention} ({member.id}) has been warned with a strike weight of {weight}."

    try:
        await member.send(
            f"You have been warned on {guild.name} with a strike value of {weight}. "
            f"After a total value of 3, permanent exclusion from the server may be enforced.\n"
            f"Following is the reason given:\n>>> {reason}\n"
        )
    except Forbidden as ex:
        message = "Could not DM member due to privacy settings, however the infraction was still added."
        logger.warning(
            f"Forbidden, when trying to contact user with ID {member.id} about infraction.",
            exc_info=ex,
        )
    except HTTPException as ex:
        message = "Here's a 400 Bad Request for you. Just like when you tried to ask me out, last week."
        logger.warning(
            f"HTTPException when trying to add infraction for user with ID {member.id}",
            exc_info=ex,
        )

    return SimpleResponse(message=message, delete_after=None)
