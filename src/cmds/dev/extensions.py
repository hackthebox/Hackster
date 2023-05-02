import logging
from enum import Enum
from functools import partial
from typing import Iterable, Optional

from discord import Interaction, WebhookMessage
from discord.commands import ApplicationContext, AutocompleteContext, Option, OptionChoice, SlashCommandGroup
from discord.errors import ExtensionAlreadyLoaded, ExtensionNotLoaded
from discord.ext import commands

from src import cmds
from src.bot import Bot
from src.core import settings
from src.utils.extensions import EXTENSIONS

log = logging.getLogger(__name__)

UNLOAD_BLACKLIST = {f"{cmds.__name__}.core.extensions"}
BASE_PATH_LEN = len(cmds.__name__.split("."))


class Action(Enum):
    """Represents an action to perform on an extension."""

    # Need to be partial otherwise they are considered to be function definitions.
    LOAD = partial(Bot.load_extension)
    UNLOAD = partial(Bot.unload_extension)
    RELOAD = partial(Bot.reload_extension)


class Extensions(commands.Cog):
    """Extension management commands."""

    def __init__(self, bot: Bot):
        self.bot = bot

    def get_extensions(self, ctx: AutocompleteContext) -> Iterable[OptionChoice]:
        """Return a list of extensions for the autocomplete."""
        verb = ctx.command.qualified_name.rsplit()[-1]
        extensions = {
            "load": EXTENSIONS - set(self.bot.extensions),
            "unload": set(self.bot.extensions) - UNLOAD_BLACKLIST,
            "reload": EXTENSIONS
        }

        results = []
        for extension in extensions[verb]:
            # Format an extension into a human-readable format.
            formatted_extension = extension.removeprefix(f"{cmds.__name__}.")

            # Select the extensions that begin with the characters entered so far.
            if formatted_extension.startswith(ctx.value.lower()):
                results.append(OptionChoice(formatted_extension, extension))

        return results

    extensions = SlashCommandGroup(
        "exts", "Load, unload and reload a bot's extension.",
        guild_ids=settings.dev_guild_ids
    )

    @extensions.command()
    async def load(
        self, ctx: ApplicationContext,
        extension: Option(
            str, "Choose an extension.",
            autocomplete=get_extensions
        )
    ) -> Interaction | WebhookMessage:
        """Load an extension given its name."""
        msg, error = await self.manage(Action.LOAD, extension)
        return await ctx.respond(msg)

    @extensions.command()
    async def unload(
        self, ctx: ApplicationContext,
        extension: Option(
            str, "Choose an extension.",
            autocomplete=get_extensions
        )
    ) -> Interaction | WebhookMessage:
        """Unload an extension given its name."""
        msg, error = await self.manage(Action.UNLOAD, extension)
        return await ctx.respond(msg)

    @extensions.command()
    async def reload(
        self, ctx: ApplicationContext,
        extension: Option(
            str, "Choose an extension.",
            autocomplete=get_extensions
        )
    ) -> Interaction | WebhookMessage:
        """Reload an extension given its name."""
        msg, error = await self.manage(Action.RELOAD, extension)
        return await ctx.respond(msg)

    async def manage(self, action: Action, ext: str) -> tuple[str, Optional[str]]:
        """Apply an action to an extension and return the status message and any error message."""
        verb = action.name.lower()
        error_msg = None

        try:
            action.value(self.bot, ext)
            # await self.bot.sync_commands()
        except (ExtensionAlreadyLoaded, ExtensionNotLoaded):
            if action is Action.RELOAD:
                # When reloading, just load the extension if it was not loaded.
                return await self.manage(Action.LOAD, ext)

            msg = f":x: Extension `{ext}` is already {verb}ed."
            log.debug(msg[4:])
        except Exception as e:
            if hasattr(e, "original"):
                e = e.original

            log.exception(f"Extension '{ext}' failed to {verb}.")

            error_msg = f"{e.__class__.__name__}: {e}"
            msg = f":x: Failed to {verb} extension `{ext}`:\n```\n{error_msg}\n```"
        else:
            msg = f":ok_hand: Extension successfully {verb}ed: `{ext}`."
            log.debug(msg[10:])

        return msg, error_msg


def setup(bot: Bot) -> None:
    """Load the `Extensions` cog."""
    bot.add_cog(Extensions(bot))
