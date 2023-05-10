import asyncio
import logging
from datetime import datetime
from typing import Coroutine

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
        self._batch = []
        self.lock = asyncio.Lock()
        self.all_tasks.start()

    @tasks.loop(count=1)
    async def all_tasks(self) -> None:
        """Gathers all scheduled tasks."""
        logger.debug("Gathering scheduled tasks...")
        await asyncio.gather(self.auto_unban(), self.auto_unmute())
        logger.debug("Scheduling completed.")

    async def auto_unban(self) -> list[Coroutine]:
        """Task to automatically unban members."""
        unban_tasks = []
        now = datetime.now()
        async with AsyncSessionLocal() as session:
            result = await session.scalars(select(Ban).filter(Ban.unbanned.is_(False)))
            bans = result.all()

        for ban in bans:
            run_at = datetime.fromtimestamp(ban.unban_time)
            logger.debug(
                "Got user_id: {user_id} and unban timestamp: {unban_ts} from DB.".format(
                    user_id=ban.user_id, unban_ts=run_at
                )
            )

            for guild_id in settings.guild_ids:
                guild = await self.bot.fetch_guild(guild_id)
                unban_tasks.append(
                    schedule(unban_member(guild, ban.user_id), run_at=run_at)
                )
                logger.info(f"Scheduled unban task for user_id {ban.user_id} at {str(run_at)}.")

        return unban_tasks

    async def auto_unmute(self) -> list[Coroutine]:
        """Task to automatically unmute members."""
        unmute_tasks = []
        now = datetime.now()
        async with AsyncSessionLocal() as session:
            result = await session.scalars(select(Mute))
            mutes = result.all()

        for mute in mutes:
            run_at = datetime.fromtimestamp(mute.unmute_time)
            logger.debug(
                "Got user_id: {user_id} and unmute timestamp: {unmute_ts} from DB.".format(
                    user_id=mute.user_id, unmute_ts=run_at
                )
            )
            # This remains as check, since we filter out those records in the query directly.
            if (run_at - now).days > 365:
                logger.info(
                    f"Skipping scheduled unmute for user_id {mute.user_id}: "
                    f"is over one years into the future ({str(run_at)})"
                )
                continue

            for guild in self.bot.guilds:
                unmute_tasks.append(
                    schedule(unmute_member(guild, mute.user_id), run_at=run_at)
                )
                logger.info(f"Scheduled unmute task for user_id {mute.user_id} at {str(run_at)}.")

        return unmute_tasks


def setup(bot: Bot) -> None:
    """Load the `ScheduledTasks` cog."""
    bot.add_cog(ScheduledTasks(bot))
