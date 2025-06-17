import logging
from typing import Dict, List, Optional

import aiohttp
import discord
from discord import Forbidden, Member, Role, User
from discord.ext.commands import GuildNotFound, MemberNotFound

from src.bot import Bot
from src.core import settings
from src.helpers.ban import BanCodes, ban_member

logger = logging.getLogger(__name__)


async def get_user_details(account_identifier: str) -> Optional[Dict]:
    """Get user details from HTB."""
    acc_id_url = f"{settings.API_URL}/discord/identifier/{account_identifier}?secret={settings.HTB_API_SECRET}"

    async with aiohttp.ClientSession() as session:
        async with session.get(acc_id_url) as r:
            if r.status == 200:
                response = await r.json()
            elif r.status == 404:
                logger.debug(
                    "Account identifier has been regenerated since last identification. Cannot re-verify."
                )
                response = None
            else:
                logger.error(
                    f"Non-OK HTTP status code returned from identifier lookup: {r.status}."
                )
                response = None

    return response


async def get_season_rank(htb_uid: int) -> str | None:
    """Get season rank from HTB."""
    headers = {"Authorization": f"Bearer {settings.HTB_API_KEY}"}
    season_api_url = f"{settings.API_V4_URL}/season/end/{settings.SEASON_ID}/{htb_uid}"

    async with aiohttp.ClientSession() as session:
        async with session.get(season_api_url, headers=headers) as r:
            if r.status == 200:
                response = await r.json()
            elif r.status == 404:
                logger.error("Invalid Season ID.")
                response = None
            else:
                logger.error(
                    f"Non-OK HTTP status code returned from identifier lookup: {r.status}."
                )
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


async def _check_for_ban(member: Member) -> Optional[Dict]:
    """Check if the member is banned."""
    try:
        member.guild.get_role(settings.roles.BANNED)
        return True
    except Forbidden:
        return False


async def process_certification(certid: str, name: str):
    """Process certifications."""
    cert_api_url = f"{settings.API_V4_URL}/certificate/lookup"
    params = {"id": certid, "name": name}
    async with aiohttp.ClientSession() as session:
        async with session.get(cert_api_url, params=params) as r:
            if r.status == 200:
                response = await r.json()
            elif r.status == 404:
                return False
            else:
                logger.error(
                    f"Non-OK HTTP status code returned from identifier lookup: {r.status}."
                )
                response = None
    try:
        certRawName = response["certificates"][0]["name"]
    except IndexError:
        return False
    if certRawName == "HTB Certified Bug Bounty Hunter":
        cert = "CBBH"
    elif certRawName == "HTB Certified Penetration Testing Specialist":
        cert = "CPTS"
    elif certRawName == "HTB Certified Defensive Security Analyst":
        cert = "CDSA"
    elif certRawName == "HTB Certified Web Exploitation Expert":
        cert = "CWEE"
    elif certRawName == "HTB Certified Active Directory Pentesting Expert":
        cert = "CAPE"
    else:
        cert = False
    return cert


async def _handle_banned_user(member: Member, bot: Bot):
    """Handle banned trait during account linking.

    Args:
        member (Member): The member to process.
        bot (Bot): The bot instance.
    """
    resp = await ban_member(
        bot,
        member.guild,
        member,
        "1337w",
        (
            "Banned on the HTB Platform. Ban duration could not be determined. "
            "Please login to confirm ban details and contact HTB Support to appeal."
        ),
        None,
        needs_approval=False,
    )
    if resp.code == BanCodes.SUCCESS:
        embed = discord.Embed(
            title="Identification error",
            description=f"User {member.mention} ({member.id}) was platform banned HTB and thus also here.",
            color=0xFF2429,
        )
        await member.guild.get_channel(settings.channels.VERIFY_LOGS).send(embed=embed)


async def _set_nickname(member: Member, nickname: str) -> bool:
    """Set the nickname of the member.

    Args:
        member (Member): The member to set the nickname for.
        nickname (str): The nickname to set.

    Returns:
        bool: True if the nickname was set, False otherwise.
    """
    try:
        await member.edit(nick=nickname)
        return True
    except Forbidden as e:
        logger.error(f"Exception whe trying to edit the nick-name of the user: {e}")
        return False


async def process_account_identification(
    member: Member, bot: Bot, traits: dict[str, str] | None = None
) -> None:
    """Process HTB account identification, to be called during account linking.

    Args:
        member (Member): The member to process.
        bot (Bot): The bot instance.
        traits (dict[str, str] | None): Optional user traits to process.
    """
    await member.add_roles(member.guild.get_role(settings.roles.VERIFIED), atomic=True)

    nickname_changed = False

    if traits.get("username") and traits.get("username") != member.name:
        nickname_changed = await _set_nickname(member, traits.get("username"))

    if not nickname_changed:
        logger.warning(
            f"No username provided for {member.name} with ID {member.id} during identification."
        )

    if traits.get("mp_user_id"):
        htb_user_details = await get_user_details(traits.get("mp_user_id"))
        await process_labs_identification(htb_user_details, member, bot)

        if not nickname_changed:
            logger.debug(
                f"Falling back on HTB username to set nickname for {member.name} with ID {member.id}."
            )
            await _set_nickname(member, htb_user_details["username"])

    if traits.get("banned", False) == True:  # noqa: E712 - explicit bool only, no truthiness
        await _handle_banned_user(member, bot)
        return


async def process_labs_identification(
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

    to_remove = []
    for role in member.roles:
        if role.id in settings.role_groups.get("ALL_RANKS") + settings.role_groups.get(
            "ALL_POSITIONS"
        ):
            to_remove.append(guild.get_role(role.id))

    to_assign = []
    if htb_user_details["rank"] not in [
        "Deleted",
        "Moderator",
        "Ambassador",
        "Admin",
        "Staff",
    ]:
        to_assign.append(
            guild.get_role(settings.get_post_or_rank(htb_user_details["rank"]))
        )

    season_rank = await get_season_rank(htb_uid)
    if season_rank:
        to_assign.append(guild.get_role(settings.get_season(season_rank)))

    if htb_user_details["vip"]:
        to_assign.append(guild.get_role(settings.roles.VIP))
    if htb_user_details["dedivip"]:
        to_assign.append(guild.get_role(settings.roles.VIP_PLUS))
    if htb_user_details["hof_position"] != "unranked":
        position = int(htb_user_details["hof_position"])
        pos_top = None
        if position == 1:
            pos_top = "1"
        elif position <= 10:
            pos_top = "10"
        if pos_top:
            to_assign.append(guild.get_role(settings.get_post_or_rank(pos_top)))
    if htb_user_details["machines"]:
        to_assign.append(guild.get_role(settings.roles.BOX_CREATOR))
    if htb_user_details["challenges"]:
        to_assign.append(guild.get_role(settings.roles.CHALLENGE_CREATOR))

    # We don't need to remove any roles that are going to be assigned again
    to_remove = list(set(to_remove) - set(to_assign))
    if to_remove:
        await member.remove_roles(*to_remove, atomic=True)
    if to_assign:
        await member.add_roles(*to_assign, atomic=True)

    return to_assign
