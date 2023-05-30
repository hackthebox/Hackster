import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import aiohttp
import discord
from discord import Forbidden, Guild, Member, Role, User
from discord.ext.commands import GuildNotFound, MemberNotFound

from src.bot import Bot
from src.core import settings
from src.helpers.ban import ban_member

logger = logging.getLogger(__name__)


async def get_user_details(account_identifier: str) -> Optional[Dict]:
    """Get user details from HTB."""
    acc_id_url = f"{settings.API_URL}/discord/identifier/{account_identifier}?secret={settings.HTB_API_SECRET}"

    async with aiohttp.ClientSession() as session:
        async with session.get(acc_id_url) as r:
            if r.status == 200:
                response = await r.json()
            elif r.status == 404:
                logger.debug("Account identifier has been regenerated since last identification. Cannot re-verify.")
                response = None
            else:
                logger.error(f"Non-OK HTTP status code returned from identifier lookup: {r.status}.")
                response = None

    return response


async def get_season_rank(htb_uid: str | int) -> str | None:
    """Get season rank from HTB."""
    if isinstance(htb_uid, str):
        htb_uid = int(htb_uid)
    headers = {"Authorization": f"Bearer {settings.HTB_API_KEY}"}
    season_api_url = f"{settings.API_V4_URL}/season/end/0/{htb_uid}"

    async with aiohttp.ClientSession() as session:
        async with session.get(season_api_url, headers=headers) as r:
            if r.status == 200:
                response = await r.json()
            elif r.status == 404:
                logger.error("Invalid Season ID.")
                response = None
            else:
                logger.error(f"Non-OK HTTP status code returned from identifier lookup: {r.status}.")
                response = None

    if not response["data"]:
        rank = None
    else:
        try:
            rank = response["data"]["season"]["tier"]
        except TypeError as exc:
            logger.error("Could not get season rank from HTB.", exc_info=exc)
            rank = None
    return rank


async def _check_for_ban(uid: str) -> Optional[Dict]:
    async with aiohttp.ClientSession() as session:
        token_url = f"{settings.API_URL}/discord/{uid}/banned?secret={settings.HTB_API_SECRET}"
        async with session.get(token_url) as r:
            if r.status == 200:
                ban_details = await r.json()
            else:
                logger.error(
                    f"Could not fetch ban details for uid {uid}: "
                    f"non-OK status code returned ({r.status}). Body: {r.content}"
                )
                ban_details = None

    return ban_details


async def process_identification(
    htb_user_details: Dict[str, str], user: Optional[Member | User], bot: Bot
) -> Optional[List[Role]]:
    """Returns roles to assign if identification was successfully processed."""

    # Retrieve necessary information from htb_user_details dictionary
    htb_uid = htb_user_details["user_id"]
    htb_user_name = htb_user_details["user_name"]

    guild, member = await _get_guild_and_member_info(bot, user)

    # Check for ban and handle accordingly
    banned_details = await _check_for_ban(htb_uid)
    if banned_details and banned_details["banned"]:
        await _handle_ban(banned_details, bot, guild, member)
        return None

    # Remove unnecessary roles
    to_remove = [
        role for role in member.roles
        if role.id in (settings.role_groups.get("ALL_RANKS") + settings.role_groups.get("ALL_POSITIONS"))
    ]

    to_assign = await _get_roles_to_assign(guild, htb_user_details)

    # Update member's nickname if necessary
    if member.nick != htb_user_name:
        try:
            await member.edit(nick=htb_user_name)
        except Forbidden as e:
            logger.error(f"Exception when trying to edit the nickname of the user: {e}")

    # Perform role assignment and removal
    to_remove = list(set(to_remove) - set(to_assign))
    if to_remove:
        await member.remove_roles(*to_remove, atomic=True)
    else:
        logger.debug("No roles need to be removed")
    if to_assign:
        await member.add_roles(*to_assign, atomic=True)
    else:
        logger.debug("No roles need to be assigned")

    return to_assign


async def _get_roles_to_assign(guild: Guild, htb_user_details: dict) -> List[Optional[Role]]:
    htb_uid = htb_user_details["user_id"]
    htb_rank = htb_user_details["rank"]
    htb_vip = htb_user_details["vip"]
    htb_dedivip = htb_user_details["dedivip"]
    htb_hof_position = htb_user_details["hof_position"]
    htb_machines = htb_user_details["machines"]
    htb_challenges = htb_user_details["challenges"]

    # Assign relevant roles based on HTB information
    to_assign = []
    if htb_rank not in ["Deleted", "Moderator", "Ambassador", "Admin", "Staff"]:
        to_assign.append(guild.get_role(settings.get_post_or_rank(htb_rank)))
    season_rank = await get_season_rank(htb_uid)
    if season_rank:
        to_assign.append(guild.get_role(settings.get_season(season_rank)))
    if htb_vip:
        to_assign.append(guild.get_role(settings.roles.VIP))
    if htb_dedivip:
        to_assign.append(guild.get_role(settings.roles.VIP_PLUS))
    if htb_hof_position != "unranked":
        pos_top = await _assign_hof_role(htb_hof_position)
        to_assign.append(guild.get_role(settings.get_post_or_rank(pos_top)))
    if htb_machines:
        to_assign.append(guild.get_role(settings.roles.BOX_CREATOR))
    if htb_challenges:
        to_assign.append(guild.get_role(settings.roles.CHALLENGE_CREATOR))
    return to_assign


async def _get_guild_and_member_info(bot: Bot, user: User | Member) -> Tuple[Guild, Member]:
    # Obtain the guild and member information
    if isinstance(user, Member):
        member = user
        guild = member.guild
    elif isinstance(user, User) and len(user.mutual_guilds) == 1:
        guild = user.mutual_guilds[0]
        member = await bot.get_member_or_user(guild, user.id)
        if not member:
            raise MemberNotFound(str(user.id))
    else:
        raise GuildNotFound(f"Could not identify member {user} in guild.")
    return guild, member


async def _assign_hof_role(htb_hof_position: str) -> str:
    position = int(htb_hof_position)
    if 1 <= position <= 100:
        if position == 1:
            pos_top = "1"
        elif position <= 5:
            pos_top = "5"
        elif position <= 10:
            pos_top = "10"
        elif position <= 25:
            pos_top = "25"
        elif position <= 50:
            pos_top = "50"
        else:
            pos_top = "100"
        logger.debug(f"User is Hall of Fame rank {position}. Assigning role Top-{pos_top}...")
        return pos_top
    else:
        logger.debug(f"User is position {position}. No Hall of Fame roles for them.")


async def _handle_ban(banned_details, bot, guild, member):
    banned_until = banned_details["ends_at"][:10]  # Extract date portion from the timestamp
    banned_until_dt = datetime.strptime(banned_until, "%Y-%m-%d")
    ban_duration = f"{(banned_until_dt - datetime.now()).days}d"
    reason = "Banned on the HTB Platform. Please contact HTB Support to appeal."
    logger.info(f"Discord user {member.name} ({member.id}) is platform banned. Banning from Discord...")
    await ban_member(bot, guild, member, ban_duration, reason, None, needs_approval=False)
    embed = discord.Embed(
        title="Identification error",
        description=f"User {member.mention} ({member.id}) was platform banned HTB and thus also here.",
        color=0xFF2429,
    )
    await guild.get_channel(settings.channels.BOT_LOGS).send(embed=embed)
