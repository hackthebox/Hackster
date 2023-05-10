"""Helper methods to handle bans, mutes and infractions. Bot or message responses are NOT allowed."""
import asyncio
import calendar
import logging
import time
from datetime import datetime

import discord
from discord import Forbidden, Guild, HTTPException, Member, NotFound
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

from src.bot import Bot
from src.core import settings
from src.database.models import Ban, Infraction, Mute
from src.database.session import AsyncSessionLocal
from src.helpers.checks import member_is_staff
from src.helpers.duration import validate_duration
from src.helpers.responses import SimpleResponse

logger = logging.getLogger(__name__)


# TODO: Clean up method, return ban record and raise BanError when something goes wrong.  # noqa: T000
async def ban_member(
    local_bot: Bot, guild: Guild, member: Member, duration: str, reason: str, author: Member = None,
    needs_approval: bool = True
) -> SimpleResponse | None:
    """Ban a member from the guild."""
    if member_is_staff(member):
        return SimpleResponse(message="You cannot ban another staff member.", delete_after=None)
    if member.bot:
        return SimpleResponse(message="You cannot ban a bot.", delete_after=None)
    if author and author.id == member.id:
        return SimpleResponse(message="You cannot ban yourself.", delete_after=None)

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
        author = local_bot.user

    ban = Ban(
        user_id=member.id, reason=reason, moderator_id=author.id, unban_time=dur,
        approved=False if needs_approval else True
    )
    infraction = Infraction(
        user_id=member.id, reason=f"Previously banned for: {reason}", weight=0, moderator_id=author.id,
        date=datetime.now().date()
    )
    async with AsyncSessionLocal() as session:
        session.add(ban)
        session.add(infraction)
        await session.commit()
    ban_id = ban.id
    assert ban_id is not None

    message = (f"You have been banned from {guild.name} until {end_date} (UTC). "
               f"To appeal the ban, please reach out to an Administrator.\n"
               f"Following is the reason given:\n>>> {reason}\n")
    try:
        await member.send(message)
    except Forbidden as ex:
        logger.warning(f"HTTPException when trying to unban user with ID {member.id}", exc_info=ex)
        if author:
            return SimpleResponse(
                message="Could not DM member due to privacy settings, however will still attempt to ban them...",
                delete_after=None
            )
        return
    except HTTPException as ex:
        logger.warning(f"HTTPException when trying to unban user with ID {member.id}: {ex}")
        if author:
            return SimpleResponse(
                message="Here's a 400 Bad Request for you. Just like when you tried to ask me out, last week.",
                delete_after=None
            )
        return

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
        logger.warning(f"HTTPException when trying to unban user with ID {member.id}", exc_info=ex)
        if author:
            return SimpleResponse(
                message="Here's a 400 Bad Request for you. Just like when you tried to ask me out, last week.",
                delete_after=None
            )
        return

    if not needs_approval:
        if member:
            message = f"Member {member.display_name} has been banned permanently."
        else:
            message = f"Member {member.id} has been banned permanently."
        logger.info(f"Member {member.id} has been banned permanently.")
        # run_at = datetime.fromtimestamp(dur)
        # unban_coro = unban_member(guild, member)
        # sch = schedule(unban_coro, run_at=run_at)

        local_bot.loop.call_later(
            int(dur - calendar.timegm(time.gmtime())), lambda: asyncio.create_task(unban_member(guild, member))
        )
        return SimpleResponse(message=message, delete_after=0)
    else:
        if member:
            message = f"{member.display_name} ({member.id}) has been banned until {end_date} (UTC)."
        else:
            message = f"{member.id} has been banned until {end_date} (UTC)."
        member_name = f"{member.name} ({member.id})"
        embed = discord.Embed(
            title=f"Ban request #{ban_id}",
            description=f"{author.name} would like to ban {member_name} until {end_date} (UTC). Reason: {reason}", )
        embed.set_thumbnail(url=f"{settings.HTB_URL}/images/logo600.png")
        embed.add_field(name="Approve duration:", value=f"/approve {ban_id}", inline=True)
        embed.add_field(name="Change duration:", value=f"/dispute {ban_id} <duration>", inline=True)
        embed.add_field(name="Deny and unban:", value=f"/deny {ban_id}", inline=True)
        await guild.get_channel(settings.channels.SR_MOD).send(embed=embed)
        return SimpleResponse(message=message, delete_after=0)


async def unban_member(guild: Guild, member: Member) -> Member | None:
    """Unban a member from the guild."""
    try:
        await guild.unban(member)
        logger.info(f"Unbanned user {member.id}.")
    except Forbidden as ex:
        logger.error(f"Permission denied when trying to unban user with ID {member.id}", exc_info=ex)
        return None
    except NotFound as ex:
        logger.error(
            f"NotFound when trying to unban user with ID {member.id}. "
            f"This could indicate that the user is not currently banned.", exc_info=ex, )
        return None
    except HTTPException as ex:
        logger.error(f"HTTPException when trying to unban user with ID {member.id}", exc_info=ex)
        return None

    async with AsyncSessionLocal() as session:
        stmt = select(Ban).filter(Ban.user_id == member.id).limit(1)
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
    # Validate reason
    if len(reason) == 0:
        reason = "No reason given ..."

    # Validate duration
    dur, dur_exc = validate_duration(duration)
    # Check if duration is valid, negative values are generally not allowed, so they should be caught here
    if dur <= 0:
        return SimpleResponse(message=dur_exc, delete_after=15)

    if member_is_staff(member):
        return SimpleResponse(message="You cannot ban another staff member.", delete_after=None)

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


async def unmute_member(guild: Guild, member: Member) -> None:
    """Unmute a member from the guild."""
    role = guild.get_role(settings.roles.MUTED)

    if member:
        # No longer on the server - cleanup, but don't attempt to remove a role
        logger.info(f"Remove mute from {member.name}:{member.id}.")
        await member.remove_roles(role)

    async with AsyncSessionLocal() as session:
        stmt = select(Mute).filter(Mute.user_id == member.id)
        result = await session.scalars(stmt)
        mute: Mute = result.first()
        if mute:
            await session.delete(mute)
            await session.commit()
        else:
            raise NoResultFound(f"Mute not found for user ID {member.id}")


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
