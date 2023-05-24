import asyncio
import logging
from datetime import datetime
from typing import Coroutine

logger = logging.getLogger(__name__)


async def schedule(task: Coroutine, run_at: datetime) -> None:
    """
    Schedule an "Awaitable" for future execution, i.e. an async function.

    For example to schedule foo(1, 2) 421337 seconds into the future:
    await schedule(foo(1, 2), at=(dt.datetime.now() + dt.timedelta(seconds=421337)))
    """
    now = datetime.now()
    delay = int((run_at - now).total_seconds())
    if delay < 0:
        logger.debug(
            "Target execution is in the past. Setting sleep timer to 0.",
            extra={
                "target_exec": repr(run_at),
                "current_time": repr(now),
            },
        )
        await task
        return

    logger.debug(
        f"Task {task.__name__} will run after {delay} seconds.",
        extra={
            "target_exec": repr(run_at),
            "current_time": repr(now),
        },
    )

    await asyncio.sleep(delay)
    await task
    return
