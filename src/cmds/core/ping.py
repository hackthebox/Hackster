import logging

import arrow
from dateutil.relativedelta import relativedelta
from discord import Embed, Interaction, WebhookMessage
from discord.commands import ApplicationContext, slash_command
from discord.ext import commands
from discord.ext.commands import cooldown

from src import start_time
from src.bot import Bot
from src.core import settings
from src.utils.formatters import color_level

log = logging.getLogger(__name__)


class PingCog(commands.Cog):
    """Get info about the bot's ping and uptime."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @slash_command(guild_ids=settings.guild_ids)
    @cooldown(1, 3600, commands.BucketType.user)
    async def ping(self, ctx: ApplicationContext) -> Interaction | WebhookMessage:
        """Ping the bot to see its latency, uptime and version."""
        difference = relativedelta(arrow.utcnow() - start_time)
        uptime: str = start_time.shift(
            seconds=-difference.seconds,
            minutes=-difference.minutes,
            hours=-difference.hours,
            days=-difference.days
        ).humanize()

        latency = round(self.bot.latency * 1000)

        embed = Embed(
            colour=color_level(latency),
            description=f"• Gateway Latency: **{latency}ms**\n• Start time: **{uptime}**\n• Version: **"
                        f"{settings.VERSION}**"
        )

        return await ctx.respond(embed=embed)


def setup(bot: Bot) -> None:
    """Load the `PingCog` cog."""
    bot.add_cog(PingCog(bot))
