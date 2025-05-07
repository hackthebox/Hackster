import logging

from src.bot import bot
from src.core import settings
from src.utils.extensions import walk_extensions
from src.webhooks.server import serve

logger = logging.getLogger(__name__)

# Load all cogs extensions.
for ext in walk_extensions():
    if ext == "src.cmds.automation.scheduled_tasks":
        continue
    bot.load_extension(ext)

if __name__ == "__main__":
    logger.info("Starting bot & webhook server")
    logger.debug(f"Starting webhook server listening on port: {settings.WEBHOOK_PORT}")
    bot.loop.create_task(serve())
    logger.debug(f"Starting bot with token: {settings.bot.TOKEN}")
    bot.loop.create_task(bot.run(settings.bot.TOKEN))
