import logging

from discord import ApplicationContext, Embed, Interaction, Message, Option, WebhookMessage, slash_command
from discord.abc import GuildChannel
from discord.ext import commands

from src.bot import Bot
from src.core import settings

logger = logging.getLogger(__name__)


class OtherCog(commands.Cog):
    """Ban related commands."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @slash_command(guild_ids=settings.guild_ids, description="A simple reply stating hints are not allowed.")
    async def no_hints(
        self, ctx: ApplicationContext
    ) -> Message:
        """A simple reply stating hints are not allowed."""
        return await channel.send(
            "No hints are allowed for the duration the event is going on. This is a competitive event with prizes. "
            "Once the event is over you are more then welcome to share solutions/write-ups/etc and try them in the "
            "After Party event."
        )

    @slash_command(guild_ids=settings.guild_ids, description="Add the URL which has spoiler link.")
    async def spoiler(self, ctx: ApplicationContext, url: str) -> Interaction | WebhookMessage:
        """Add the URL which has spoiler link."""
        if len(url) == 0:
            return await ctx.respond("Please provide the spoiler URL.")

        embed = Embed(title="Spoiler Report", color=0xB98700)
        embed.add_field(name=f"{ctx.user} has submitted a spoiler.", value=f"URL: <{url}>", inline=False)

        channel = self.bot.get_channel(settings.channels.SPOILER)
        await channel.send(embed=embed)
        return await ctx.respond("Thanks for the reporting the spoiler.", ephemeral=True, delete_after=15)


def setup(bot: Bot) -> None:
    """Load the `ChannelManageCog` cog."""
    bot.add_cog(OtherCog(bot))
