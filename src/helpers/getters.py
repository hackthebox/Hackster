import logging
from functools import singledispatch

from discord import Bot, Forbidden, Guild, HTTPException, Member, User

logger = logging.getLogger(__name__)


@singledispatch
async def get_member_safe(member: Member | User | int | str, guild: Guild) -> Member:
    """Get a member from a user or member ID or mention."""
    logger.error("Inside signgledispatch of get_member_safe")
    raise NotImplementedError("Implement process for get_user_safe")


@get_member_safe.register
async def _(member: Member, guild: Guild = None) -> Member:
    logger.debug(f"Attempting to get member by type {type(member)}")
    return member


@get_member_safe.register
async def _(user: User, guild: Guild) -> Member | None:
    logger.debug(f"Attempting to get user by type {type(user)}")
    try:
        member = await guild.fetch_member(user.id)
    except Forbidden as exc:
        logger.warning(f"Unauthorized attempt to fetch member with id: {user.id}", exc_info=exc)
        return
    except HTTPException as exc:
        logger.error(f"Discord error while fetching guild member with id: {user.id}", exc_info=exc)
        return
    return member


@get_member_safe.register
async def _(user_id: str | int, guild: Guild) -> Member | None:
    logger.debug(f"Attempting to get user_id by type {type(user_id)}")
    try:
        user_id = int(user_id)
    except ValueError:
        logger.error(f"Invalid user id: {user_id}")

    try:
        member = await guild.fetch_member(user_id)
    except Forbidden as exc:
        logger.warning(f"Unauthorized attempt to fetch member with id: {user_id}", exc_info=exc)
        return
    except HTTPException as exc:
        logger.error(f"Discord error while fetching guild member with id: {user_id}", exc_info=exc)
        return
    return member


@singledispatch
async def get_user_safe(user: User | Member | int | str, bot: Bot):
    """Get a user from a user ID or mention."""
    logger.error("Inside signgledispatch of get_user_safe")
    raise NotImplementedError("Implement process for get_user_safe")


@get_user_safe.register
async def _(user: User | Member, bot: Bot = None) -> User:
    logger.debug(f"Attempting to get user by type {type(user)}")
    return user


@get_user_safe.register
async def _(user_id: str, bot: Bot) -> User | None:
    logger.debug("Attempting to get user by type str")
    try:
        user_id = int(user_id.replace("<@", "").replace("!", "").replace(">", ""))
        return await bot.fetch_user(user_id)
    except KeyError as exc:
        logger.debug(f"Could not find user by id: {user_id}", exc_info=exc)
    except ValueError as exc:
        logger.debug(f"Error getting user, invalid id: {user_id}", exc_info=exc)


@get_user_safe.register
async def _(user_id: int, bot: Bot) -> User | None:
    logger.debug("Attempting to get user by type int")
    try:
        return await bot.fetch_user(user_id)
    except KeyError as exc:
        logger.debug(f"Could not find user by id: {user_id}", exc_info=exc)
    except ValueError as exc:
        logger.debug(f"Error getting user, invalid id: {user_id}", exc_info=exc)
