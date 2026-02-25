import asyncio
import logging
from datetime import datetime, timedelta, timezone

from discord import Member
from discord.ext import commands, tasks
from sqlalchemy import select

from src import settings
from src.bot import Bot
from src.database.models import Ban, MinorReport, Mute
from src.database.session import AsyncSessionLocal
from src.helpers.ban import unban_member, unmute_member
from src.helpers.minor_verification import (
    APPROVED,
    CONSENT_VERIFIED,
    assign_minor_role,
    years_until_18,
)
from src.helpers.schedule import schedule

logger = logging.getLogger(__name__)


class ScheduledTasks(commands.Cog):
    """Cog for handling scheduled tasks."""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.all_tasks.start()

    @tasks.loop(minutes=1)
    async def all_tasks(self) -> None:
        """Gathers all scheduled tasks."""
        logger.debug("Gathering scheduled tasks...")
        await self.auto_unban()
        await self.auto_unmute()
        await self.auto_remove_minor_role()
        logger.debug("Scheduling completed.")

    async def auto_unban(self) -> None:
        """Task to automatically unban members."""
        unban_tasks = []
        unban_time = datetime.timestamp(datetime.now() + timedelta(minutes=1)) * 1000
        logger.debug(f"Checking for bans to remove until {unban_time}.")
        async with AsyncSessionLocal() as session:
            result = await session.scalars(
                select(Ban).filter(Ban.unbanned.is_(False)).filter(Ban.unban_time <= unban_time)
            )
            bans = result.all()
            logger.debug(f"Got {len(bans)} bans from DB.")

        for guild_id in settings.guild_ids:
            logger.debug(f"Running for guild: {guild_id}.")
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Unable to find guild with ID {guild_id}.")
                continue

            for ban in bans:
                run_at = datetime.fromtimestamp(ban.unban_time)
                logger.debug(
                    f"Got user_id: {ban.user_id} and unban timestamp: {run_at} from DB."
                )
                member = await self.bot.get_member_or_user(guild, ban.user_id)
                if not member:
                    logger.info(f"Member with id: {ban.user_id} not found.")
                    continue
                unban_task = schedule(unban_member(guild, member), run_at=run_at)
                unban_tasks.append(unban_task)
                logger.info(f"Scheduled unban task for user_id {ban.user_id} at {run_at}.")

        await asyncio.gather(*unban_tasks)

    async def auto_unmute(self) -> None:
        """Task to automatically unmute members."""
        unmute_tasks = []
        unmute_time = datetime.timestamp(datetime.now() + timedelta(minutes=1)) * 1000
        logger.debug(f"Checking for mutes to remove until {unmute_time}.")
        async with AsyncSessionLocal() as session:
            result = await session.scalars(select(Mute).filter(Mute.unmute_time <= unmute_time))
            mutes = result.all()
            logger.debug(f"Got {len(mutes)} mutes from DB.")

        for guild_id in settings.guild_ids:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Unable to find guild with ID {guild_id}.")
                continue

            for mute in mutes:
                run_at = datetime.fromtimestamp(mute.unmute_time)
                logger.debug(
                    "Got user_id: {user_id} and unmute timestamp: {unmute_ts} from DB.".format(
                        user_id=mute.user_id, unmute_ts=run_at
                    )
                )
                member = await self.bot.get_member_or_user(guild, mute.user_id)
                if not member:
                    logger.info(f"Member with id: {mute.user_id} not found.")
                    continue
                unmute_task = schedule(unmute_member(guild, member), run_at=run_at)
                unmute_tasks.append(unmute_task)
                logger.info(f"Scheduled unban task for user_id {mute.user_id} at {str(run_at)}.")


        await asyncio.gather(*unmute_tasks)

    async def auto_remove_minor_role(self) -> None:
        """Remove minor role from users who have reached 18 based on report data."""
        logger.debug("Checking for minor roles to remove based on age.")
        now = datetime.now(timezone.utc)

        async with AsyncSessionLocal() as session:
            result = await session.scalars(
                select(MinorReport).filter(MinorReport.status.in_([APPROVED, CONSENT_VERIFIED]))
            )
            reports = result.all()

        for guild_id in settings.guild_ids:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Unable to find guild with ID {guild_id} for minor role cleanup.")
                continue

            for report in reports:
                # Compute approximate 18th birthday based on suspected age at report time.
                created_at = report.created_at
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                years = years_until_18(report.suspected_age)
                expires_at = created_at + timedelta(days=365 * years)
                if now < expires_at:
                    continue

                member: Member | None = await self.bot.get_member_or_user(guild, report.user_id)
                if not member:
                    continue

                role_id = settings.roles.VERIFIED_MINOR
                role = guild.get_role(role_id)
                if not role or role not in member.roles:
                    continue

                logger.info(
                    "Removing minor role from user %s (%s) because they have reached 18.",
                    member,
                    member.id,
                )
                try:
                    await member.remove_roles(role, atomic=True)
                except Exception as exc:
                    logger.warning(
                        "Failed to remove minor role from %s (%s): %s", member, member.id, exc
                    )

    @commands.Cog.listener()
    async def on_member_join(self, member: Member) -> None:
        """Assign minor role on rejoin if consent is verified and they are still under 18."""
        async with AsyncSessionLocal() as session:
            result = await session.scalars(
                select(MinorReport).filter(
                    MinorReport.user_id == member.id,
                    MinorReport.status == CONSENT_VERIFIED,
                )
            )
            report = result.first()

        if not report:
            return

        now = datetime.now(timezone.utc)
        created_at = report.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        years = years_until_18(report.suspected_age)
        expires_at = created_at + timedelta(days=365 * years)
        if now >= expires_at:
            return

        await assign_minor_role(member, member.guild)


def setup(bot: Bot) -> None:
    """Load the `ScheduledTasks` cog."""
    bot.add_cog(ScheduledTasks(bot))
