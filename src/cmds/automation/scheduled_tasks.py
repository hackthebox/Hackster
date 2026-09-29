import asyncio
import logging
from collections.abc import Coroutine
from datetime import datetime, timedelta

from discord.ext import commands, tasks
from sqlalchemy import select
from sqlalchemy.exc import NoResultFound

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
        self._pending_tasks: set[asyncio.Task] = set()
        self.all_tasks.start()

    def _track_task(self, coro: Coroutine) -> None:
        """Retain a background task so it is not garbage-collected while it sleeps."""
        task = asyncio.create_task(coro)
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _run_scheduled(self, action: Coroutine, run_at: datetime, kind: str) -> None:
        """Run a ban or mute removal at `run_at` without blocking the scheduler loop."""
        try:
            await schedule(action, run_at=run_at)
        except NoResultFound:
            logger.info("Scheduled %s skipped; the record was already cleared.", kind)
        except Exception:
            logger.exception("Scheduled %s failed.", kind)

    @staticmethod
    def _due_before_epoch() -> int:
        """
        Return the unix-second cutoff for records due within the next minute.

        unban_time and unmute_time are stored as seconds. A millisecond cutoff
        would select every row, including bans years in the future.
        """
        return int((datetime.now() + timedelta(minutes=1)).timestamp())

    @tasks.loop(minutes=1)
    async def all_tasks(self) -> None:
        """Schedule due unbans and unmutes without waiting for them to finish."""
        logger.debug("Gathering scheduled tasks...")
        try:
            await self.auto_unban()
            await self.auto_unmute()
        except Exception:
            logger.exception("Failed while scheduling unbans or unmutes.")
        logger.debug("Scheduling completed.")

    async def auto_unban(self) -> None:
        """Schedule removal of bans that expire within the next minute."""
        due_before = self._due_before_epoch()
        logger.debug(f"Checking for bans to remove until {due_before}.")
        async with AsyncSessionLocal() as session:
            result = await session.scalars(
                select(Ban).filter(Ban.unbanned.is_(False)).filter(Ban.unban_time <= due_before)
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
                try:
                    run_at = datetime.fromtimestamp(ban.unban_time)
                except (OverflowError, OSError, ValueError):
                    logger.exception(
                        "Invalid unban_time %s for user_id %s.", ban.unban_time, ban.user_id
                    )
                    continue
                logger.debug(f"Got user_id: {ban.user_id} and unban timestamp: {run_at} from DB.")
                member = await self.bot.get_member_or_user(guild, ban.user_id)
                if not member:
                    logger.info(f"Member with id: {ban.user_id} not found.")
                    continue
                self._track_task(self._run_scheduled(unban_member(guild, member), run_at, "unban"))
                logger.info(f"Scheduled unban task for user_id {ban.user_id} at {run_at}.")

    async def auto_unmute(self) -> None:
        """Schedule removal of mutes that expire within the next minute."""
        due_before = self._due_before_epoch()
        logger.debug(f"Checking for mutes to remove until {due_before}.")
        async with AsyncSessionLocal() as session:
            result = await session.scalars(select(Mute).filter(Mute.unmute_time <= due_before))
            mutes = result.all()
            logger.debug(f"Got {len(mutes)} mutes from DB.")

        for guild_id in settings.guild_ids:
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Unable to find guild with ID {guild_id}.")
                continue

            for mute in mutes:
                try:
                    run_at = datetime.fromtimestamp(mute.unmute_time)
                except (OverflowError, OSError, ValueError):
                    logger.exception(
                        "Invalid unmute_time %s for user_id %s.", mute.unmute_time, mute.user_id
                    )
                    continue
                logger.debug(
                    "Got user_id: {user_id} and unmute timestamp: {unmute_ts} from DB.".format(
                        user_id=mute.user_id, unmute_ts=run_at
                    )
                )
                member = await self.bot.get_member_or_user(guild, mute.user_id)
                if not member:
                    logger.info(f"Member with id: {mute.user_id} not found.")
                    continue
                self._track_task(self._run_scheduled(unmute_member(guild, member), run_at, "unmute"))
                logger.info(f"Scheduled unmute task for user_id {mute.user_id} at {run_at}.")


def setup(bot: Bot) -> None:
    """Load the `ScheduledTasks` cog."""
    bot.add_cog(ScheduledTasks(bot))
