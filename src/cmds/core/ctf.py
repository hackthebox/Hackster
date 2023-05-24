import asyncio
import logging

import discord
from discord import ApplicationContext, CategoryChannel, Interaction, SlashCommandGroup, TextChannel, WebhookMessage
from discord.commands import Option
from discord.ext import commands
from discord.ext.commands import has_any_role
from sqlalchemy import select

from src.bot import Bot
from src.core import settings
from src.database.models import Ctf
from src.database.session import AsyncSessionLocal

CTF_RULES = """
Do not attack the backend infrastructure of the CTF.
Do not attack other teams playing in the CTF.
Do not brute-force the flag submission form.
Do not exchange flags or write-ups/hints of the challenges with other teams.
Do not violate HTB's Terms of Service. You can read it here.
Do not try to DDoS the challenges or make actions that could lead to this result. For example, brute force or use of
automated tools with many threads.
Do not be part of more than one team within the same CTF.
"""  # noqa: E501

logger = logging.getLogger(__name__)


class CtfCog(commands.Cog):
    """CTF related commands."""

    def __init__(self, bot: Bot):
        self.bot = bot

    ctf = SlashCommandGroup("ctf", "Manage CTF channels and let people joint them.", guild_ids=settings.guild_ids)

    @ctf.command(description="Create CTF channels")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_SR_MODS"))
    async def create(
        self,
        ctx: ApplicationContext,
        ctf_name: Option(str, "The name of the event to join"),
        ctf_pass: Option(str, "The password for the event"),
    ) -> Interaction | WebhookMessage:
        """Create CTF channels."""
        if len(ctf_pass) < 5:
            logger.info(f"Whoops, the password was too short! Password was only {len(ctf_pass)} characters...")
            return await ctx.respond("The password must be longer than 4 characters")

        async def create_channel(
            _ctf_name: str, channel_name: str, category: CategoryChannel, overwrites: dict, position: int
        ) -> TextChannel | None:
            try:
                logger.debug(f"Creating {channel_name} channel ...")
                channel = await ctx.guild.create_text_channel(
                    f"{_ctf_name}-{channel_name}", category=category, overwrites=overwrites, position=position
                )
                return channel
            except Exception as _exc:
                logger.critical(f"Error creating {channel_name} channel!", exc_info=_exc)

        ctf_name = ctf_name.lower()
        async with ctx.typing():
            logger.info(f"Creating CTF {ctf_name}...")
            await ctx.respond(f"Creating CTF {ctf_name}...")
            # Create the Two Roles
            admin = ctx.guild.create_role(name=f"{ctf_name}-Admin", mentionable=False)
            part = ctx.guild.create_role(name=f"{ctf_name}-Participant", mentionable=False)
            try:
                logger.debug("Creating CTF roles...")
                admin, part = await asyncio.gather(admin, part)
            except Exception as exc:
                logger.critical("Error creating roles!", exc_info=exc)
                return await ctx.respond("Error creating roles!")
            guild = ctx.guild
            htb_staff_role = guild.get_role(settings.roles.HTB_STAFF)

            # Assign permissions to roles
            logger.debug("Assigning permissions for roles ...")
            admin_rw_part_r = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                admin: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                part: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                htb_staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            }
            ctf_only = {
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                admin: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
                part: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
                htb_staff_role: discord.PermissionOverwrite(
                    read_messages=True, send_messages=True, read_message_history=True
                ),
            }

            _list = await ctx.guild.create_category(ctf_name)
            rules = await create_channel(ctf_name, "rules", _list, admin_rw_part_r, 0)
            announcements = await create_channel(ctf_name, "announcements", _list, ctf_only, 1)
            await create_channel(ctf_name, "general", _list, ctf_only, 2)
            await create_channel(ctf_name, "support", _list, ctf_only, 3)

            try:
                logger.debug("Generating webhook...")
                webhook = await announcements.create_webhook(name=f"{ctf_name}-webhook")
                await ctx.respond(f"Here is the webhook generated for the CTF Announcements channel! {webhook.url}")
                await rules.send(CTF_RULES)
            except Exception as exc:
                logger.error("Error generating webhook.", exc_info=exc)

            logger.info(f"Finished creating channels and roles for CTF {ctf_name}.")

            logger.info("Create CTF configuration in DB.")
            ctf = Ctf(
                name=ctf_name,
                guild_id=ctx.guild.id,
                admin_role_id=admin.id,
                participant_role_id=part.id,
                password=ctf_pass,
            )
            async with AsyncSessionLocal() as session:
                session.add(ctf)
                await session.commit()
            return await ctx.respond(f"CTF {ctf_name} has been created.")

    @ctf.command(description="Delete CTF channels")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_SR_MODS"))
    async def delete(
        self, ctx: ApplicationContext, ctf_name: Option(str, "The name of the event to join")
    ) -> Interaction | WebhookMessage:
        """Delete CTF channels."""
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(Ctf).filter(Ctf.name == ctf_name)
                result = await session.scalars(stmt)
                ctf: Ctf = result.first()
                await session.delete(ctf)
                await session.commit()
        except Exception as exc:
            logger.exception(f"Something bad happened when trying to delete '{ctf_name}'!", exc_info=exc)
            return await ctx.respond("Failed to delete CTF record from DB. Contact Bot Administrator.")

        try:
            logger.debug(f'Deleting channels and roles for "{ctf_name}"')
            ctf_name = ctf_name.lower()
            channel_rules = discord.utils.get(ctx.guild.channels, name=f"{ctf_name}-rules")
            channel_announcements = discord.utils.get(ctx.guild.channels, name=f"{ctf_name}-announcements")
            channel_support = discord.utils.get(ctx.guild.channels, name=f"{ctf_name}-support")
            channel_general = discord.utils.get(ctx.guild.channels, name=f"{ctf_name}-general")
            channel_cat = discord.utils.get(ctx.guild.categories, name=f"{ctf_name}")
            admin_role = discord.utils.get(ctx.guild.roles, name=f"{ctf_name}-Admin")
            par_role = discord.utils.get(ctx.guild.roles, name=f"{ctf_name}-Participant")
            await asyncio.gather(
                channel_announcements.delete(),
                channel_rules.delete(),
                channel_support.delete(),
                channel_general.delete(),
                channel_cat.delete(),
                admin_role.delete(),
                par_role.delete(),
            )
            logger.debug(f"Done deleting channels and roles for '{ctf_name}'")
        except Exception as exc:
            logger.error("Failed to delete a channel or role.", exc_info=exc)
            return await ctx.respond("Failed to delete channels and/or roles. Manual action required.")
        return await ctx.respond(f"CTF {ctf_name} has been deleted.")

    @ctf.command(description="Join CTF channels")
    async def join(
        self,
        ctx: ApplicationContext,
        ctf_name: Option(str, "The name of the event to join"),
        ctf_pass: Option(str, "The password for the event"),
    ) -> Interaction | WebhookMessage:
        """Join CTF channels."""
        # try:
        ctx.defer()
        ctf_name = ctf_name.lower()
        async with AsyncSessionLocal() as session:
            stmt = select(Ctf).filter(Ctf.name == ctf_name)
            result = await session.scalars(stmt)
            ctf: Ctf = result.first()
        if not ctf:
            return await ctx.respond("The specified CTF is invalid.", ephemeral=True)
        if not isinstance(ctf_pass, str):
            return await ctx.respond(ctx, "Invalid Password!", ephemeral=True)

        if ctf_pass == ctf.password:
            # Passwords matched - add roles
            member = await self.bot.get_member_or_user(ctx.guild, ctx.user.id)
            await member.add_roles(ctx.guild.get_role(ctf.participant_role_id))
            return await ctx.respond(f"You've been added to {ctf.name}", ephemeral=True)
        else:
            logger.debug(
                f"User {ctx.user.mention} provided an invalid password for the CTF {ctf_name}. "
                f'Supplied password (masked): {"*" * len(ctf_pass)}'
            )
            return await ctx.respond("Invalid Password!", ephemeral=True)


def setup(bot: Bot) -> None:
    """Load the `CtfCog` cog."""
    bot.add_cog(CtfCog(bot))
