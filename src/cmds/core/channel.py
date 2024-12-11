import logging

from discord import ApplicationContext, Interaction, Option, WebhookMessage, slash_command
from discord.abc import GuildChannel
from discord.ext import commands
from discord.ext.commands import has_any_role

from src.bot import Bot
from src.core import settings

logger = logging.getLogger(__name__)


class ChannelCog(commands.Cog):
    """Ban related commands."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @slash_command(
        guild_ids=settings.guild_ids,
        description="Add slow-mode to the channel. Specifying a value of 0 removes the slow-mode again."
    )
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_MODS"))
    async def slowmode(
        self, ctx: ApplicationContext, channel: GuildChannel, seconds: int
    ) -> Interaction | WebhookMessage:
        """Add slow-mode to the channel. Specifying a value of 0 removes the slow-mode again."""
        guild = ctx.guild

        if isinstance(channel, str):
            try:
                channel_id = int(channel.replace("<#", "").replace(">", ""))
                channel = guild.get_channel(channel_id)
            except ValueError:
                return await ctx.respond(
                    f"I don't know what {channel} is. Please use #channel-reference or a channel ID."
                )

        try:
            seconds = int(seconds)
        except ValueError:
            return await ctx.respond(f"Malformed amount of seconds: {seconds}.")

        if seconds < 0:
            seconds = 0
        if seconds > 30:
            seconds = 30
        await channel.edit(slowmode_delay=seconds)
        return await ctx.respond(f"Slow-mode set in {channel.name} to {seconds} seconds.")

    @slash_command(guild_ids=settings.guild_ids)
    @has_any_role(
        *settings.role_groups.get("ALL_ADMINS"),
        *settings.role_groups.get("ALL_SR_MODS"),
        *settings.role_groups.get("ALL_MODS")
    )
    async def cleanup(
        self, ctx: ApplicationContext,
        count: Option(int, "How many messages to delete", required=True, default=5),
    ) -> Interaction | WebhookMessage:
        """Removes the past X messages!"""
        await ctx.channel.purge(limit=count + 1, bulk=True, check=lambda m: m != ctx.message)
        # Don't delete the command that triggered this deletion
        return await ctx.respond(f"Deleted {count} messages.", ephemeral=True)


def setup(bot: Bot) -> None:
    """Load the `ChannelManageCog` cog."""
    bot.add_cog(ChannelCog(bot))
