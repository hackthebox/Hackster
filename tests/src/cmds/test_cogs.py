"""Test suite for general tests which apply to all cogs."""

import importlib
from collections import defaultdict
from types import ModuleType
from typing import Iterator

from discord.commands import SlashCommand
from discord.ext import commands

from src.utils.extensions import walk_extensions


class TestCommandName:
    """Tests for shadowing command names and aliases."""

    @staticmethod
    def walk_cogs(module: ModuleType) -> Iterator[commands.Cog]:
        """Yield all cogs defined in an extension."""
        for obj in module.__dict__.values():
            # Check if it's a class type cause otherwise issubclass() may raise a TypeError.
            is_cog = isinstance(obj, type) and issubclass(obj, commands.Cog)
            if is_cog and obj.__module__ == module.__name__:
                yield obj

    @staticmethod
    def walk_commands(cog: commands.Cog) -> Iterator[SlashCommand]:
        """An iterator that recursively walks through `cog`'s commands and subcommands."""
        # Can't use Bot.walk_commands() or Cog.get_commands() cause those are instance methods.
        for cmd in cog.__cog_commands__:
            if cmd.parent is None:
                yield cmd
                if isinstance(cmd, commands.GroupMixin):
                    # Annoyingly it returns duplicates for each alias so use a set to fix that.
                    yield from set(cmd.walk_commands())

    def get_all_commands(self) -> Iterator[SlashCommand]:
        """Yield all commands for all cogs in all extensions."""
        for ext in walk_extensions():
            module = importlib.import_module(ext)
            for cog in self.walk_cogs(module):
                for cmd in self.walk_commands(cog):
                    cmd.cog = cog  # Should explicitly assign the cog object.
                    yield cmd

    def test_names_dont_shadow(self):
        """Names and aliases of commands should be unique."""
        all_names = defaultdict(list)
        for cmd in self.get_all_commands():
            try:
                func_name = f"{cmd.cog.__module__}.{cmd.callback.__qualname__}"
            except AttributeError:
                # If `cmd` is a SlashCommandGroup.
                func_name = f"{cmd.cog.__module__}.{cmd.name}"

            name = cmd.qualified_name

            if name in all_names:
                conflicts = ", ".join(all_names.get(name, ""))
                raise NameError(f"Name '{name}' of the command {func_name} conflicts with {conflicts}.")

            all_names[name].append(func_name)
