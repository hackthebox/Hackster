import logging
import traceback
from typing import Dict, List, Optional, Any, TypeVar

import aiohttp
import discord
from discord import (
    ApplicationContext,
    Forbidden,
    HTTPException,
    Member,
    Role,
    User,
    Guild,
)
from discord.ext.commands import GuildNotFound, MemberNotFound

from src.bot import Bot, BOT_TYPE

from src.core import settings
from src.helpers.ban import BanCodes, ban_member, _send_ban_notice

logger = logging.getLogger(__name__)


async def send_verification_instructions(
    ctx: ApplicationContext, member: Member
) -> discord.Interaction | discord.WebhookMessage:
    """Send instructions via DM on how to identify with HTB account.

    Args:
        ctx (ApplicationContext): The context of the command.
        member (Member): The member to send the instructions to.

    Returns:
        discord.Interaction | discord.WebhookMessage: The response message.
    """
    member = ctx.user

    # Create step-by-step instruction embeds
    embed_step1 = discord.Embed(color=0x9ACC14)
    embed_step1.add_field(
        name="Step 1: Login to your HTB Account",
        value="Go to <https://account.hackthebox.com/> and login.",
        inline=False,
    )
    embed_step1.set_image(
        url="https://media.discordapp.net/attachments/1102700815493378220/1384587341338902579/image.png"
    )

    embed_step2 = discord.Embed(color=0x9ACC14)
    embed_step2.add_field(
        name="Step 2: Navigate to your Security Settings",
        value="In the navigation bar, click on **Security Settings** and scroll down to the **Discord Account** section. "
        "(<https://account.hackthebox.com/security-settings>)",
        inline=False,
    )
    embed_step2.set_image(
        url="https://media.discordapp.net/attachments/1102700815493378220/1384587813760270392/image.png"
    )

    embed_step3 = discord.Embed(color=0x9ACC14)
    embed_step3.add_field(
        name="Step 3: Link your Discord Account",
        value="Click **Connect** and you will be redirected to login to your Discord account via oauth. "
        "After logging in, you will be redirected back to the HTB Account page. "
        "Your Discord account will now be linked. Discord may take a few minutes to update. "
        "If you have any issues, please contact a Moderator.",
        inline=False,
    )
    embed_step3.set_image(
        url="https://media.discordapp.net/attachments/1102700815493378220/1384586811384402042/image.png"
    )

    try:
        await member.send(embed=embed_step1)
        await member.send(embed=embed_step2)
        await member.send(embed=embed_step3)
    except Forbidden as ex:
        logger.error("Exception during verify call", exc_info=ex)
        return await ctx.respond(
            "Whoops! I cannot DM you after all due to your privacy settings. Please allow DMs from other server "
            "members and try again in 1 minute."
        )
    except HTTPException as ex:
        logger.error("Exception during verify call.", exc_info=ex)
        return await ctx.respond(
            "An unexpected error happened (HTTP 400, bad request). Please contact an Administrator."
        )

    return await ctx.respond("Please check your DM for instructions.", ephemeral=True)



def get_labs_session() -> aiohttp.ClientSession:
    """Get a session for the HTB Labs API."""
    return aiohttp.ClientSession(headers={"Authorization": f"Bearer {settings.HTB_API_KEY}"})


async def get_user_details(labs_id: int | str) -> dict:
    """Get user details from HTB."""

    if not labs_id:
        return {}
    
    user_profile_api_url = f"{settings.API_V4_URL}/user/profile/basic/{labs_id}"
    user_content_api_url = f"{settings.API_V4_URL}/user/profile/content/{labs_id}"

    async with get_labs_session() as session:
        async with session.get(user_profile_api_url) as r:
            if r.status == 200:
                profile_response = await r.json()
            else:
                logger.error(
                    f"Non-OK HTTP status code returned from user details lookup: {r.status}."
                )
                profile_response = {}

        async with session.get(user_content_api_url) as r:
            if r.status == 200:
                content_response = await r.json()
            else:
                logger.error(
                    f"Non-OK HTTP status code returned from user content lookup: {r.status}."
                )
                content_response = {}

    profile = profile_response.get("profile", {})
    profile["content"] = content_response.get("profile", {}).get("content", {})
    return profile


async def get_season_rank(htb_uid: int) -> str | None:
    """Get season rank from HTB."""
    season_api_url = f"{settings.API_V4_URL}/season/end/{settings.SEASON_ID}/{htb_uid}"

    async with get_labs_session() as session:
        async with session.get(season_api_url) as r:
            if r.status == 200:
                response = await r.json()
            elif r.status == 404:
                logger.error("Invalid Season ID.")
                response = {}
            else:
                logger.error(
                    f"Non-OK HTTP status code returned from identifier lookup: {r.status}."
                )
                response = {}

    if not response["data"]:
        rank = None
    else:
        try:
            rank = response["data"]["season"]["tier"]
        except TypeError as exc:
            logger.error("Could not get season rank from HTB.", exc_info=exc)
            rank = None
    return rank


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
                response = {}
    try:
        certRawName = response["certificates"][0]["name"]
    except IndexError:
        return False
    if certRawName == "HTB Certified Bug Bounty Hunter":
        cert = "CBBH"
    elif certRawName == "HTB Certified Web Exploitation Specialist":
        cert = "CBBH"
    elif certRawName == "HTB Certified Penetration Testing Specialist":
        cert = "CPTS"
    elif certRawName == "HTB Certified Defensive Security Analyst":
        cert = "CDSA"
    elif certRawName == "HTB Certified Web Exploitation Expert":
        cert = "CWEE"
    elif certRawName == "HTB Certified Active Directory Pentesting Expert":
        cert = "CAPE"
    elif certRawName == "HTB Certified Junior Cybersecurity Associate":
        cert = "CJCA"
    else:
        cert = False
    return cert


async def _handle_banned_user(member: Member, bot: BOT_TYPE):
    """Handle banned trait during account linking.

    Args:
        member (Member): The member to process.
        bot (Bot): The bot instance.
    """
    resp = await ban_member(
        bot,  # type: ignore
        member.guild,
        member,
        "1337w",
        (
            "Platform Ban - Ban duration could not be determined. "
            "Please login to confirm ban details and contact HTB Support to appeal."
        ),
        "N/A",
        None,  
        needs_approval=False,
    )
    if resp.code == BanCodes.SUCCESS:
        await _send_ban_notice(
            member.guild,
            member,
            resp.message,
            "System",
            "1337w",
            member.guild.get_channel(settings.channels.VERIFY_LOGS),  # type: ignore
        )


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
    member: Member, bot: BOT_TYPE, traits: dict[str, Any]
) -> None:
    """Process HTB account identification, to be called during account linking.

    Args:
        member (Member): The member to process.
        bot (Bot): The bot instance.
        traits (dict[str, str] | None): Optional user traits to process.
    """
    try:
        await member.add_roles(member.guild.get_role(settings.roles.VERIFIED), atomic=True)  # type: ignore
    except Exception as e:
        logger.error(f"Failed to add VERIFIED role to user {member.id}: {e}")
        # Don't raise - continue with other operations

    nickname_changed = False

    traits = traits or {}

    if traits.get("username") and traits.get("username") != member.name:
        nickname_changed = await _set_nickname(member, traits.get("username"))  # type: ignore

    if not nickname_changed:
        logger.warning(
            f"No username provided for {member.name} with ID {member.id} during identification."
        )

    if traits.get("mp_user_id"):
        try:
            logger.debug(f"MP user ID: {traits.get('mp_user_id', None)}")
            htb_user_details = await get_user_details(traits.get("mp_user_id", None))
            if htb_user_details:
                await process_labs_identification(htb_user_details, member, bot)  # type: ignore

                if not nickname_changed and htb_user_details.get("username"):
                    logger.debug(
                        f"Falling back on HTB username to set nickname for {member.name} with ID {member.id}."
                    ) 
                    await _set_nickname(member, htb_user_details["username"])
        except Exception as e:
            logger.error(f"Failed to process labs identification for user {member.id}: {e}")
            # Don't raise - this is not critical

    if traits.get("banned", False) == True:  # noqa: E712 - explicit bool only, no truthiness
        try:
            logger.debug(f"Handling banned user {member.id}")
            await _handle_banned_user(member, bot)
            return
        except Exception as e:
            logger.error(f"Failed to handle banned user {member.id}: {e}")
            logger.exception(traceback.format_exc())
            # Don't raise - continue processing


async def process_labs_identification(
    htb_user_details: dict, user: Optional[Member | User], bot: Bot
) -> Optional[List[Role]]:
    """Returns roles to assign if identification was successfully processed."""
    
    # Resolve member and guild
    member, guild = await _resolve_member_and_guild(user, bot)
    
    # Get roles to remove and assign
    to_remove = _get_roles_to_remove(member, guild)
    to_assign = await _process_role_assignments(htb_user_details, guild)
    
    # Remove roles that will be reassigned
    to_remove = list(set(to_remove) - set(to_assign))
    
    # Apply role changes
    await _apply_role_changes(member, to_remove, to_assign)
    
    return to_assign


async def _resolve_member_and_guild(
    user: Optional[Member | User], bot: Bot
) -> tuple[Member, Guild]:
    """Resolve member and guild from user object."""
    if isinstance(user, Member):
        return user, user.guild
    
    if isinstance(user, User) and len(user.mutual_guilds) == 1:
        guild = user.mutual_guilds[0]
        member = await bot.get_member_or_user(guild, user.id)
        if not member:
            raise MemberNotFound(str(user.id))
        return member, guild  # type: ignore
    
    raise GuildNotFound(f"Could not identify member {user} in guild.")


def _get_roles_to_remove(member: Member, guild: Guild) -> list[Role]:
    """Get existing roles that should be removed."""
    to_remove = []
    try:
        all_ranks = settings.role_groups.get("ALL_RANKS", [])
        all_positions = settings.role_groups.get("ALL_POSITIONS", [])
        removable_role_ids = all_ranks + all_positions
        
        for role in member.roles:
            if role.id in removable_role_ids:
                guild_role = guild.get_role(role.id)
                if guild_role:
                    to_remove.append(guild_role)
    except Exception as e:
        logger.error(f"Error processing existing roles for user {member.id}: {e}")
    return to_remove


async def _process_role_assignments(
    htb_user_details: dict, guild: Guild
) -> list[Role]:
    """Process role assignments based on HTB user details."""
    to_assign = []
    
    # Process rank roles
    to_assign.extend(_process_rank_roles(htb_user_details.get("rank", ""), guild))
    
    # Process season rank roles
    to_assign.extend(await _process_season_rank_roles(htb_user_details.get("id", ""), guild))
    
    # Process VIP roles
    to_assign.extend(_process_vip_roles(htb_user_details, guild))
    
    # Process HOF position roles
    to_assign.extend(_process_hof_position_roles(htb_user_details.get("ranking", "unranked"), guild))
    
    # Process creator roles
    to_assign.extend(_process_creator_roles(htb_user_details.get("content", {}), guild))
    
    return to_assign


def _process_rank_roles(rank: str, guild: Guild) -> list[Role]:
    """Process rank-based role assignments."""
    roles = []
    
    if rank and rank not in ["Deleted", "Moderator", "Ambassador", "Admin", "Staff"]:
        role_id = settings.get_post_or_rank(rank)
        if role_id:
            role = guild.get_role(role_id)
            if role:
                roles.append(role)
    
    return roles


async def _process_season_rank_roles(mp_user_id: int, guild: Guild) -> list[Role]:
    """Process season rank role assignments."""
    roles = []
    try:
        season_rank = await get_season_rank(mp_user_id)
        if isinstance(season_rank, str):
            season_role_id = settings.get_season(season_rank)
            if season_role_id:
                season_role = guild.get_role(season_role_id)
                if season_role:
                    roles.append(season_role)
    except Exception as e:
        logger.error(f"Error getting season rank for user {mp_user_id}: {e}")
    return roles


def _process_vip_roles(htb_user_details: dict, guild: Guild) -> list[Role]:
    """Process VIP role assignments."""
    roles = []
    try:
        if htb_user_details.get("isVip", False):
            vip_role = guild.get_role(settings.roles.VIP)
            if vip_role:
                roles.append(vip_role)
        
        if htb_user_details.get("isDedicatedVip", False):
            vip_plus_role = guild.get_role(settings.roles.VIP_PLUS)
            if vip_plus_role:
                roles.append(vip_plus_role)
    except Exception as e:
        logger.error(f"Error processing VIP roles: {e}")
    return roles


def _process_hof_position_roles(htb_user_ranking: str | int, guild: Guild) -> list[Role]:
    """Process Hall of Fame position role assignments."""
    roles = []
    try:
        hof_position = htb_user_ranking or "unranked"
        logger.debug(f"HTB user ranking: {hof_position}")
        if hof_position != "unranked":
            position = int(hof_position)
            pos_top = _get_position_tier(position)
            
            if pos_top:
                pos_role_id = settings.get_post_or_rank(pos_top)
                if pos_role_id:
                    pos_role = guild.get_role(pos_role_id)
                    if pos_role:
                        roles.append(pos_role)
    except (ValueError, TypeError) as e:
        logger.error(f"Error processing HOF position: {e}")
    return roles


def _get_position_tier(position: int) -> Optional[str]:
    """Get position tier based on HOF position."""
    if position == 1:
        return "1"
    elif position <= 10:
        return "10"
    return None


def _process_creator_roles(htb_user_content: dict, guild: Guild) -> list[Role]:
    """Process creator role assignments."""
    roles = []
    try:
        if htb_user_content.get("machines"):
            box_creator_role = guild.get_role(settings.roles.BOX_CREATOR)
            if box_creator_role:
                logger.debug("Adding box creator role to user.")
                roles.append(box_creator_role)
        
        if htb_user_content.get("challenges"):
            challenge_creator_role = guild.get_role(settings.roles.CHALLENGE_CREATOR)
            if challenge_creator_role:
                logger.debug("Adding challenge creator role to user.")
                roles.append(challenge_creator_role)
        
        if htb_user_content.get("sherlocks"):
            sherlock_creator_role = guild.get_role(settings.roles.SHERLOCK_CREATOR)
            if sherlock_creator_role:
                logger.debug("Adding sherlock creator role to user.")
                roles.append(sherlock_creator_role)
    except Exception as e:
        logger.error(f"Error processing creator roles: {e}")
    return roles


async def _apply_role_changes(
    member: Member, to_remove: list[Role], to_assign: list[Role]
) -> None:
    """Apply role changes to member."""
    try:
        if to_remove:
            await member.remove_roles(*to_remove, atomic=True)
    except Exception as e:
        logger.error(f"Error removing roles from user {member.id}: {e}")
    
    try:
        if to_assign:
            await member.add_roles(*to_assign, atomic=True)
    except Exception as e:
        logger.error(f"Error adding roles to user {member.id}: {e}")
