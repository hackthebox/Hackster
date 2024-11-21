"""Helper methods to handle bans, mutes and infractions. Bot or message responses are NOT allowed."""
import asyncio
import logging
from datetime import datetime

import discord
from discord import Forbidden, Guild, HTTPException, Member, NotFound, User
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


async def _check_member(bot: Bot, guild: Guild, member: Member | User, author: Member = None) -> SimpleResponse | None:
    if isinstance(member, Member):
        if member_is_staff(member):
            return SimpleResponse(message="You cannot ban another staff member.", delete_after=None)
    elif isinstance(member, User):
        member = await bot.get_member_or_user(guild, member.id)
    if member.bot:
        return SimpleResponse(message="You cannot ban a bot.", delete_after=None)
    if author and author.id == member.id:
        return SimpleResponse(message="You cannot ban yourself.", delete_after=None)


async def _get_ban_or_create(member: Member, ban: Ban, infraction: Infraction) -> tuple[int, bool]:
    async with AsyncSessionLocal() as session:
        stmt = select(Ban).filter(Ban.user_id == member.id, Ban.unbanned.is_(False)).limit(1)
        result = await session.scalars(stmt)
        existing_ban = result.first()
        if existing_ban:
            return existing_ban.id, True

        session.add(ban)
        session.add(infraction)
        await session.commit()
    ban_id: int = ban.id
    assert ban_id is not None
    return ban_id, False


async def ban_member(
    bot: Bot, guild: Guild, member: Member | User, duration: str, reason: str, evidence: str, author: Member = None,
    needs_approval: bool = True
) -> SimpleResponse | None:
    """Ban a member from the guild."""
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
    else:
        end_date: str = datetime.utcfromtimestamp(dur).strftime("%Y-%m-%d %H:%M:%S")

    if author is None:
        author = bot.user

    ban = Ban(
        user_id=member.id, reason=reason, moderator_id=author.id, unban_time=dur,
        approved=False if needs_approval else True
    )
    infraction = Infraction(
        user_id=member.id, reason=f"Previously banned for: {reason}", weight=0, moderator_id=author.id,
        date=datetime.now().date()
    )
    ban_id, is_existing = await _get_ban_or_create(member, ban, infraction)
    if is_existing:
        return SimpleResponse(
            message=f"A ban with id: {ban_id} already exists for member {member}",
            delete_after=None
        )

    # DM member, before we ban, else we cannot dm since we do not share a guild
    dm_banned_member = await _dm_banned_member(end_date, guild, member, reason)
    # Try to actually ban the member from the guild
    try:
        await guild.ban(member, reason=reason, delete_message_days=0)
    except Forbidden as exc:
        logger.warning(
            "Ban failed due to permission error", exc_info=exc,
            extra={"ban_requestor": author.name, "ban_receiver": member.id}
        )
        if author:
            return SimpleResponse(message="You do not have the proper permissions to ban.", delete_after=None)
        return
    except HTTPException as ex:
        logger.warning(f"HTTPException when trying to ban user with ID {member.id}", exc_info=ex)
        if author:
            return SimpleResponse(
                message="Here's a 400 Bad Request for you. Just like when you tried to ask me out, last week.",
                delete_after=None
            )
        return

    # If approval is required, send a message to the moderator channel about the ban
    if not needs_approval:
        if member:
            message = f"Member {member.display_name} has been banned permanently."
        else:
            message = f"Member {member.id} has been banned permanently."

        if not dm_banned_member:
            message += "\n Could not DM banned member due to permission error."

        logger.info(
            "Member has been banned permanently.",
            extra={"ban_requestor": author.name, "ban_receiver": member.id, "dm_banned_member": dm_banned_member}
        )

        unban_task = schedule(unban_member(guild, member), run_at=ban.unban_time)
        asyncio.create_task(unban_task)
        logger.debug("Unbanned sceduled for ban", extra={"ban_id": ban_id, "unban_time": ban.unban_time})
        return SimpleResponse(message=message, delete_after=0)
    else:
        if member:
            message = f"{member.display_name} ({member.id}) has been banned until {end_date} (UTC)."
        else:
            message = f"{member.id} has been banned until {end_date} (UTC)."

        if not dm_banned_member:
            message += " Could not DM banned member due to permission error."

        member_name = f"{member.display_name} ({member.name})"
        embed = discord.Embed(
            title=f"Ban request #{ban_id}",
            description=f"{author.display_name} ({author.name}) would like to ban {member_name} until {end_date} (UTC). \n Reason: {reason} \n Evidence: {evidence}", )
        embed.set_thumbnail(url=f"{settings.HTB_URL}/images/logo600.png")
        view = BanDecisionView(ban_id, bot, guild, member, end_date, reason)
        await guild.get_channel(settings.channels.SR_MOD).send(embed=embed, view=view)
        return SimpleResponse(message=message)


async def _dm_banned_member(end_date: str, guild: Guild, member: Member, reason: str) -> bool:
    """Send a message to the member about the ban."""
    message = (f"You have been banned from {guild.name} until {end_date} (UTC). "
               f"To appeal the ban, please reach out to an Administrator.\n"
               f"Following is the reason given:\n>>> {reason}\n")
    try:
        await member.send(message)
        return True
    except Forbidden as ex:
        logger.warning(
            f"Could not DM member with id {member.id} due to privacy settings, however will still attempt to ban "
            f"them...",
            exc_info=ex
        )
    except HTTPException as ex:
        logger.warning(f"HTTPException when trying to unban user with ID {member.id}", exc_info=ex)
    return False


async def unban_member(guild: Guild, member: Member) -> Member:
    """Unban a member from the guild."""
    try:
        await guild.unban(member)
        logger.info(f"Unbanned user {member.id}.")
    except Forbidden as ex:
        logger.error(f"Permission denied when trying to unban user with ID {member.id}", exc_info=ex)
    except NotFound as ex:
        logger.error(
            f"NotFound when trying to unban user with ID {member.id}. "
            f"This could indicate that the user is not currently banned.", exc_info=ex, )
    except HTTPException as ex:
        logger.error(f"HTTPException when trying to unban user with ID {member.id}", exc_info=ex)

    async with AsyncSessionLocal() as session:
        stmt = select(Ban).filter(Ban.user_id == member.id).filter(Ban.unbanned.is_(False)).limit(1)
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
    bot: Bot, guild: Guild, member: Member, duration: str, reason: str, author: Member = None
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
            user_id=member.id, reason=reason, moderator_id=author.id, date=datetime.fromtimestamp(dur)
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

    infraction = Infraction(user_id=member.id, reason=reason, weight=weight, moderator_id=author.id)
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
        message = "Could not DM member due to privacy settings, however will still attempt to ban them..."
        logger.warning(f"Forbidden, when trying to contact user with ID {member.id} about infraction.", exc_info=ex)
    except HTTPException as ex:
        message = "Here's a 400 Bad Request for you. Just like when you tried to ask me out, last week."
        logger.warning(f"HTTPException when trying to add infraction for user with ID {member.id}", exc_info=ex)

    return SimpleResponse(message=message, delete_after=None)
