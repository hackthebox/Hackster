import logging

from discord import ApplicationContext, Interaction, Message, Option, WebhookMessage
from discord.ext import commands
from discord.ext.commands import BucketType, Cog, check_any, cooldown, has_any_role, slash_command

from src.bot import Bot
from src.core import settings

logger = logging.getLogger(__name__)


def is_user_id(required_user_id: int) -> any:  # noqa: T000 TODO: search for correct typings
    """Checks if the person executing command has a specific user_id."""
    def predicate(ctx: ApplicationContext) -> any:  # noqa: T000 TODO: search for correct typings
        return ctx.message.author.id == required_user_id
    return commands.check(predicate)


class Fun(Cog):
    """Fun commands."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @slash_command(guild_ids=settings.guild_ids, name="ban-song")
    @cooldown(1, 60, BucketType.user)
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_SR_MODS"))
    async def ban_song(self, ctx: ApplicationContext) -> Interaction | WebhookMessage:
        """Ban ban ban ban ban ..."""
        return await ctx.respond("https://www.youtube.com/watch?v=FXPKJUE86d0")

    @slash_command(guild_ids=settings.guild_ids)
    @cooldown(1, 60, BucketType.user)
    async def google(
        self, ctx: ApplicationContext, query: Option(str, "What do you need help googling?")
    ) -> Interaction | WebhookMessage:
        """Let me google that for you!"""
        goggle = query
        goggle = goggle.replace("@", "")
        goggle = goggle.replace(" ", "%20")
        goggle = goggle.replace("&", "")
        goggle = goggle.replace("<", "")
        goggle = goggle.replace(">", "")
        return await ctx.respond(f"https://lmgtfy.com?q={goggle}")

    @slash_command(guild_ids=settings.guild_ids, name="start-here", default_permission=True)
    @cooldown(1, 60, BucketType.user)
    async def start_here(self, ctx: ApplicationContext) -> Interaction | WebhookMessage:
        """Get Started."""
        return await ctx.respond(
            "Get Started with the HTB Beginners Bible: https://www.hackthebox.com/blog/learn-to-hack-beginners-bible"
        )

    @slash_command(guild_ids=settings.guild_ids, name="noah-ping")
    @check_any(
        has_any_role(*settings.role_groups.get("ALL_ADMINS"), *settings.role_groups.get("ALL_MODS")),
        is_user_id(249533661144285185)  # noqa: T000 TODO: make this a variable inside the settings.
    )
    async def noah_ping(self, ctx: ApplicationContext) -> Message:
        """@noahgang new pictures are here!"""
        return await ctx.respond(f"<@&{settings.roles.NOAH_GANG}>")


def setup(bot: Bot) -> None:
    """Load the `Fun` cog."""
    bot.add_cog(Fun(bot))
