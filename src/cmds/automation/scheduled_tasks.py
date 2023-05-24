import asyncio
import logging
from datetime import datetime, timedelta

from discord.ext import commands, tasks
from sqlalchemy import select

from src import settings
from src.bot import Bot
from src.database.models import Ban, Mute
from src.database.session import AsyncSessionLocal
from src.helpers.ban import unban_member, unmute_member
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
        # await asyncio.gather(self.auto_unmute())
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

        for ban in bans:
            run_at = datetime.fromtimestamp(ban.unban_time)
            logger.debug(
                f"Got user_id: {ban.user_id} and unban timestamp: {run_at} from DB."
            )

            for guild_id in settings.guild_ids:
                logger.debug(f"Running for guild: {guild_id}.")
                guild = self.bot.get_guild(guild_id)
                if guild:
                    member = await self.bot.get_member_or_user(guild, ban.user_id)
                    unban_task = schedule(unban_member(guild, member), run_at=run_at)
                    unban_tasks.append(unban_task)
                    logger.info(f"Scheduled unban task for user_id {ban.user_id} at {run_at}.")
                else:
                    logger.warning(f"Unable to find guild with ID {guild_id}.")

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

        for mute in mutes:
            run_at = datetime.fromtimestamp(mute.unmute_time)
            logger.debug(
                "Got user_id: {user_id} and unmute timestamp: {unmute_ts} from DB.".format(
                    user_id=mute.user_id, unmute_ts=run_at
                )
            )

            for guild_id in settings.guild_ids:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    member = await self.bot.get_member_or_user(guild, mute.user_id)
                    unmute_task = schedule(unmute_member(guild, member), run_at=run_at)
                    unmute_tasks.append(unmute_task)
                    logger.info(f"Scheduled unban task for user_id {mute.user_id} at {str(run_at)}.")
                else:
                    logger.warning(f"Unable to find guild with ID {guild_id}.")

        await asyncio.gather(*unmute_tasks)


def setup(bot: Bot) -> None:
    """Load the `ScheduledTasks` cog."""
    bot.add_cog(ScheduledTasks(bot))
