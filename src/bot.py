import logging
import socket
from abc import ABC

import discord
from aiohttp import AsyncResolver, ClientSession, TCPConnector
from discord import ApplicationContext, Cog, DiscordException, Embed, HTTPException
from discord.ext.commands import (
    Bot as DiscordBot, CommandNotFound, CommandOnCooldown, DefaultHelpCommand,
    MissingAnyRole, MissingPermissions, MissingRequiredArgument, NoPrivateMessage, UserInputError,
)
from sqlalchemy.exc import NoResultFound

from src import trace_config
from src.core import constants, settings
from src.metrics import completed_commands, errored_commands, received_commands

log = logging.getLogger(__name__)


class Bot(DiscordBot, ABC):
    """Base bot class."""

    name = settings.bot.NAME

    def __init__(self, mock: bool = False, **kwargs):
        """
        Initiate the client with slash commands.

        Args:
            mock (bool): Whether to mock the client or not.
        """
        super().__init__(**kwargs)
        if not mock:
            log.debug("Starting the HTTP session")
            self.http_session = ClientSession(
                connector=TCPConnector(resolver=AsyncResolver(), family=socket.AF_INET), trace_configs=[trace_config]
            )
        else:
            log.debug("Mocking the HTTP session")
            self.http_session = None

    async def on_ready(self) -> None:
        """Triggered when the bot is ready."""
        name = f"{self.user} (ID: {self.user.id})"

        devlog_msg = f"Connected {constants.emojis.partying_face}"
        self.loop.create_task(self.send_log(devlog_msg, colour=constants.colours.bright_green))

        log.info(f"Started bot as {name}")

    async def on_application_command(self, ctx: ApplicationContext) -> None:
        """A global handler cog."""
        log.debug(f"Command '{ctx.command}' received.")
        received_commands.labels(ctx.command.name).inc()

    async def on_application_command_error(self, ctx: ApplicationContext, error: DiscordException) -> None:
        """A global error handler cog."""
        message = None
        if isinstance(error, CommandNotFound):
            return
        if isinstance(error, MissingRequiredArgument):
            message = f"Parameter '{error.param.name}' is required, but missing. Type `{ctx.clean_prefix}help " \
                      f"{ctx.invoked_with}` for help."
        elif isinstance(error, MissingPermissions):
            message = "You are missing the required permissions to run this command."
        elif isinstance(error, MissingAnyRole):
            message = "You are not authorized to use that command."
        elif isinstance(error, UserInputError):
            message = "Something about your input was wrong, please check your input and try again."
        elif isinstance(error, NoPrivateMessage):
            message = "This command cannot be run in a DM."
        elif isinstance(error, CommandOnCooldown):
            message = f"You are on cooldown. Try again in {error.retry_after:.2f}s"
        elif isinstance(error, NoResultFound):
            message = f"The requested object could not be found."

        errored_commands.labels(ctx.command.name).inc()

        if message is None:
            raise error
        else:
            log.debug(f"A user caused an error which was handled.", exc_info=error)
            await ctx.respond(message, delete_after=15, ephemeral=True)

    async def on_application_command_completion(self, ctx: ApplicationContext) -> None:
        """A global cog handler."""
        log.debug(f"Command '{ctx.command}' completed.")
        completed_commands.labels(ctx.command.name).inc()

    async def on_error(self, event: any, *args, **kwargs) -> None:
        """Don't ignore the error, causing Sentry to capture it."""
        raise

    def add_cog(self, cog: Cog, *, override: bool = False) -> None:
        """Log whenever a cog is loaded."""
        super().add_cog(cog, override=override)
        log.debug(f"Cog loaded: {cog.qualified_name}")

    async def send_log(self, description: str = None, colour: int = None, embed: Embed = None) -> None:
        """Send an embed message to the devlog channel."""
        devlog = self.get_channel(settings.channels.DEVLOG)

        if not devlog:
            log.debug(
                f"Fetching the devlog channel as it wasn't found in the cache "
                f"(ID: {settings.channels.DEVLOG})"
            )
            try:
                devlog = await self.fetch_channel(settings.channels.DEVLOG)
            except HTTPException:
                log.debug(
                    f"Could not fetch the devlog channel so log message won't be sent "
                    f"(ID: {settings.channels.DEVLOG})"
                )
                return

        if not embed:
            embed = Embed(description=description)

        if colour:
            embed.colour = colour

        await devlog.send(embed=embed)

    async def close(self) -> None:
        """Triggered when the bot is closed."""
        await super().close()

        if self.http_session:
            log.debug("Closing the HTTP session")
            await self.http_session.close()


# Initiate the bot.
intents = discord.Intents.all()
help_command = DefaultHelpCommand(no_category="Available Commands")
bot = Bot(help_command=help_command, intents=intents)
