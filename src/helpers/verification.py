import logging
from datetime import datetime
from typing import Dict, List, Optional, cast

import aiohttp
import discord
from discord import Forbidden, Member, Role, User
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


async def get_season_rank(htb_uid: int) -> str | None:
    """Get season rank from HTB."""
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

async def process_certification(certid: str, name: str):
    cert_api_url = f"{settings.API_V4_URL}/certificate/lookup"
    params = {'id': certid, 'name': name}
    async with aiohttp.ClientSession() as session:
        async with session.get(cert_api_url, params=params) as r:
            if r.status == 200:
                response = await r.json()
            elif r.status == 404:
                return False
            else:
                logger.error(f"Non-OK HTTP status code returned from identifier lookup: {r.status}.")
                response = None

    certRawName = response['certificates']['name']
    if certRawName == "HTB Certified Bug Bounty Hunter":
        cert = "CBBH"
    elif certRawName == "HTB Certified Penetration Tester":
        cert = "CPTS"
    else:
        cert = False
    return cert


async def process_identification(
    htb_user_details: Dict[str, str], user: Optional[Member | User], bot: Bot
) -> Optional[List[Role]]:
    """Returns roles to assign if identification was successfully processed."""
    htb_uid = htb_user_details["user_id"]
    if isinstance(user, Member):
        member = user
        guild = member.guild
    # This will only work if the user and the bot share only one guild.
    elif isinstance(user, User) and len(user.mutual_guilds) == 1:
        guild = user.mutual_guilds[0]
        member = await bot.get_member_or_user(guild, user.id)
        if not member:
            raise MemberNotFound(str(user.id))
    else:
        raise GuildNotFound(f"Could not identify member {user} in guild.")
    season_rank = await get_season_rank(htb_uid)
    banned_details = await _check_for_ban(htb_uid)

    if banned_details is not None and banned_details["banned"]:
        # If user is banned, this field must be a string
        # Strip date e.g. from "2022-01-31T11:00:00.000000Z"
        banned_until: str = cast(str, banned_details["ends_at"])[:10]
        banned_until_dt: datetime = datetime.strptime(banned_until, "%Y-%m-%d")
        ban_duration: str = f"{(banned_until_dt - datetime.now()).days}d"
        reason = "Banned on the HTB Platform. Please contact HTB Support to appeal."
        logger.info(f"Discord user {member.name} ({member.id}) is platform banned. Banning from Discord...")
        await ban_member(bot, guild, member, ban_duration, reason, None, needs_approval=False)

        embed = discord.Embed(
            title="Identification error",
            description=f"User {member.mention} ({member.id}) was platform banned HTB and thus also here.",
            color=0xFF2429, )

        await guild.get_channel(settings.channels.VERIFY_LOGS).send(embed=embed)
        return None

    to_remove = []

    for role in member.roles:
        if role.id in settings.role_groups.get("ALL_RANKS") + settings.role_groups.get("ALL_POSITIONS"):
            to_remove.append(guild.get_role(role.id))

    to_assign = []
    logger.debug(
        "Getting role 'rank':", extra={
            "role_id": settings.get_post_or_rank(htb_user_details["rank"]),
            "role_obj": guild.get_role(settings.get_post_or_rank(htb_user_details["rank"])),
            "htb_rank": htb_user_details["rank"],
        }, )
    if htb_user_details["rank"] not in ["Deleted", "Moderator", "Ambassador", "Admin", "Staff"]:
        to_assign.append(guild.get_role(settings.get_post_or_rank(htb_user_details["rank"])))
    if season_rank:
        to_assign.append(guild.get_role(settings.get_season(season_rank)))
    if htb_user_details["vip"]:
        logger.debug(
            'Getting role "VIP":', extra={"role_id": settings.roles.VIP, "role_obj": guild.get_role(settings.roles.VIP)}
        )
        to_assign.append(guild.get_role(settings.roles.VIP))
    if htb_user_details["dedivip"]:
        logger.debug(
            'Getting role "VIP+":',
            extra={"role_id": settings.roles.VIP_PLUS, "role_obj": guild.get_role(settings.roles.VIP_PLUS)}
        )
        to_assign.append(guild.get_role(settings.roles.VIP_PLUS))
    if htb_user_details["hof_position"] != "unranked":
        position = int(htb_user_details["hof_position"])
        pos_top = None
        if position == 1:
            pos_top = "1"
        elif position <= 10:
            pos_top = "10"
        if pos_top:
            logger.debug(f"User is Hall of Fame rank {position}. Assigning role Top-{pos_top}...")
            logger.debug(
                'Getting role "HoF role":', extra={
                    "role_id": settings.get_post_or_rank(pos_top),
                    "role_obj": guild.get_role(settings.get_post_or_rank(pos_top)), "hof_val": pos_top,
                }, )
            to_assign.append(guild.get_role(settings.get_post_or_rank(pos_top)))
        else:
            logger.debug(f"User is position {position}. No Hall of Fame roles for them.")
    if htb_user_details["machines"]:
        logger.debug(
            'Getting role "BOX_CREATOR":',
            extra={"role_id": settings.roles.BOX_CREATOR, "role_obj": guild.get_role(settings.roles.BOX_CREATOR)}, )
        to_assign.append(guild.get_role(settings.roles.BOX_CREATOR))
    if htb_user_details["challenges"]:
        logger.debug(
            'Getting role "CHALLENGE_CREATOR":', extra={
                "role_id": settings.roles.CHALLENGE_CREATOR,
                "role_obj": guild.get_role(settings.roles.CHALLENGE_CREATOR),
            }, )
        to_assign.append(guild.get_role(settings.roles.CHALLENGE_CREATOR))

    if member.nick != htb_user_details["user_name"]:
        try:
            await member.edit(nick=htb_user_details["user_name"])
        except Forbidden as e:
            logger.error(f"Exception whe trying to edit the nick-name of the user: {e}")

    logger.debug("All roles to_assign:", extra={"to_assign": to_assign})
    # We don't need to remove any roles that are going to be assigned again
    to_remove = list(set(to_remove) - set(to_assign))
    logger.debug("All roles to_remove:", extra={"to_remove": to_remove})
    if to_remove:
        await member.remove_roles(*to_remove, atomic=True)
    else:
        logger.debug("No roles need to be removed")
    if to_assign:
        await member.add_roles(*to_assign, atomic=True)
    else:
        logger.debug("No roles need to be assigned")

    return to_assign
