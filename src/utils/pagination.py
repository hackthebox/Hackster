import asyncio
import logging
from typing import Optional

from discord import Embed, Member, Reaction
from discord.abc import User
from discord.commands import ApplicationContext
from discord.ext.commands import Paginator

from src.core import constants

FIRST_EMOJI = constants.emojis.track_previous
LEFT_EMOJI = constants.emojis.arrow_left
RIGHT_EMOJI = constants.emojis.arrow_right
LAST_EMOJI = constants.emojis.track_next
LOCK_EMOJI = constants.emojis.lock

PAGINATION_EMOJIS = (FIRST_EMOJI, LEFT_EMOJI, RIGHT_EMOJI, LAST_EMOJI, LOCK_EMOJI)

log = logging.getLogger(__name__)


class EmptyPaginatorEmbedError(Exception):
    """Base Exception class for an empty paginator embed."""


class LinePaginator(Paginator):
    """A class that aids in paginating code blocks for Discord messages."""

    def __init__(
        self,
        prefix: str = '```',
        suffix: str = '```',
        max_size: int = 2000,
        max_lines: Optional[int] = None,
        linesep: str = "\n"
    ):
        """
        Overrides the Paginator.__init__ from inside discord.ext.commands.

        `prefix` and `suffix` will be prepended and appended respectively to every page.
        `max_size` and `max_lines` denote the maximum amount of codepoints and lines
        allowed per page.
        """
        super().__init__(
            prefix,
            suffix,
            max_size - len(suffix),
            linesep
        )

        self.max_lines = max_lines
        self._current_page = [prefix]
        self._linecount = 0
        self._count = len(prefix) + 1  # prefix + newline.
        self._pages = []

    def add_line(self, line: str = "", *, empty: bool = False) -> None:
        """
        Adds a line to the current page.

        If the line exceeds the `max_size` then a RuntimeError is raised.
        Overrides the Paginator.add_line from inside discord.ext.commands in order to allow
        configuration of the maximum number of lines per page.
        If `empty` is True, an empty line will be placed after the given `line`.
        """
        if len(line) > self.max_size - len(self.prefix) - 2:
            raise RuntimeError(f"Line exceeds maximum page size {self.max_size - len(self.prefix) - 2}")

        if self.max_lines is not None:
            if self._linecount >= self.max_lines:
                self._linecount = 0
                self.close_page()

            self._linecount += 1
        if self._count + len(line) + 1 > self.max_size:
            self.close_page()

        self._count += len(line) + 1
        self._current_page.append(line)

        if empty:
            self._current_page.append("")
            self._count += 1

    @classmethod
    async def paginate(
        cls, lines: list[str], ctx: ApplicationContext, embed: Embed,
        prefix: str = "", suffix: str = "", max_lines: Optional[int] = None,
        max_size: int = constants.pagination.max_size, empty: bool = True,
        restrict_to_user: User = None, timeout: int = constants.pagination.timeout,
        footer_text: str = None, url: str = None,
        exception_on_empty_embed: bool = False
    ) -> None:
        """
        Use a paginator and set of reactions to provide pagination over a set of lines.

        The reactions are used to switch page, or to finish with pagination.
        When used, this will send a message using `ctx.respond()` and apply a set of reactions to it.
        These reactions may be used to change page, or to remove pagination from the message.
        Pagination will also be removed automatically if no reaction is added for `timeout` seconds,
        defaulting to five minutes (300 seconds).
        If `empty` is True, an empty line will be placed between each given line.
        """

        def event_check(reaction_: Reaction, user_: Member) -> bool:
            """Make sure that this reaction is what we want to operate on."""
            no_restrictions = (
                not restrict_to_user  # Pagination is not restricted.
                or user_.id == restrict_to_user.id  # The reaction was by a whitelisted user.
            )

            # Conditions for a successful pagination:
            return all(
                (
                    reaction_.message.id == message.id,  # Reaction is on this message.
                    reaction_.emoji in PAGINATION_EMOJIS,  # Reaction is one of the pagination emotes.
                    user_.id != ctx.bot.user.id,  # Reaction was not made by the Bot.
                    no_restrictions  # There were no restrictions.
                )
            )

        paginator = cls(prefix=prefix, suffix=suffix, max_size=max_size, max_lines=max_lines)
        current_page = 0

        if not lines:
            if exception_on_empty_embed:
                log.exception("Pagination asked for empty lines iterable")
                raise EmptyPaginatorEmbedError("No lines to paginate")

            log.debug("No lines to add to paginator, adding '(nothing to display)' message")
            lines.append("(nothing to display)")

        for line in lines:
            try:
                paginator.add_line(line, empty=empty)
            except Exception:
                log.exception(f"Failed to add line to paginator: '{line}'")
                raise  # Should propagate.

        embed.description = paginator.pages[current_page]

        if len(paginator.pages) <= 1:
            if footer_text:
                embed.set_footer(text=footer_text)

            if url:
                embed.url = url

            log.debug("There's less than two pages, so we won't paginate - sending single page on its own")
            await ctx.respond(embed=embed)
            return

        if footer_text:
            embed.set_footer(text=f"{footer_text} (Page {current_page + 1}/{len(paginator.pages)})")
        else:
            embed.set_footer(text=f"Page {current_page + 1}/{len(paginator.pages)}")

        if url:
            embed.url = url

        await ctx.respond(embed=embed)
        message = await ctx.interaction.original_message()

        log.debug(f"Paginator created with {len(paginator.pages)} pages (ID: {message.id})")

        for emoji in PAGINATION_EMOJIS:
            # Add all the applicable emoji to the message.
            await message.add_reaction(emoji)

        while True:
            try:
                reaction, user = await ctx.bot.wait_for("reaction_add", timeout=timeout, check=event_check)
            except asyncio.TimeoutError:
                log.debug(f"Timed out waiting for a reaction (ID: {message.id})")
                break  # We're done, no reactions for the last 5 minutes.

            # Deletes the users reaction.
            await message.remove_reaction(reaction.emoji, user)

            reaction_type = ""
            if reaction.emoji == LOCK_EMOJI:
                log.debug(f"Got lock reaction (ID: {message.id})")
                break

            elif reaction.emoji == FIRST_EMOJI:
                if current_page == 0:
                    log.debug(f"Got first page reaction, but we're on the first page - ignoring (ID: {message.id})")
                    continue

                current_page = 0
                reaction_type = "first"

            elif reaction.emoji == LAST_EMOJI:
                if current_page >= len(paginator.pages) - 1:
                    log.debug(f"Got last page reaction, but we're on the last page - ignoring (ID: {message.id})")
                    continue

                current_page = len(paginator.pages) - 1
                reaction_type = "last"

            elif reaction.emoji == LEFT_EMOJI:
                if current_page <= 0:
                    log.debug(f"Got previous page reaction, but we're on the first page - ignoring (ID: {message.id})")
                    continue

                current_page -= 1
                reaction_type = "previous"

            elif reaction.emoji == RIGHT_EMOJI:
                if current_page >= len(paginator.pages) - 1:
                    log.debug(f"Got next page reaction, but we're on the last page - ignoring (ID: {message.id})")
                    continue

                current_page += 1
                reaction_type = "next"

            # Magic happens here, after page and reaction_type is set.
            embed.description = ""
            await message.edit(embed=embed)
            embed.description = paginator.pages[current_page]

            if footer_text:
                embed.set_footer(text=f"{footer_text} (Page {current_page + 1}/{len(paginator.pages)})")
            else:
                embed.set_footer(text=f"Page {current_page + 1}/{len(paginator.pages)}")

            page = f"{current_page + 1}/{len(paginator.pages)}"
            log.debug(f"Got {reaction_type} page reaction - changing to page {page} (ID: {message.id})")

            await message.edit(embed=embed)

        log.debug(f"Ending pagination and clearing reactions... (ID: {message.id})")
        await message.clear_reactions()


class ImagePaginator(Paginator):
    """
    Helper class that paginates images for embeds in messages.

    Close resemblance to LinePaginator, except focuses on images over text.
    Refer to ImagePaginator.paginate for documentation on how to use.
    """

    def __init__(self, prefix: str = "", suffix: str = ""):
        super().__init__(prefix, suffix)
        self._count = 0
        self._current_page = [prefix]
        self.images = []
        self._pages = []

    def add_line(self, line: str = "", *, empty: bool = False) -> None:
        """
        Adds a line to each page, usually just 1 line in this ApplicationContext.

        If `empty` is True, an empty line will be placed after a given `line`.
        """
        self._count += len(line)

        self._current_page.append(line)
        self.close_page()

    def add_image(self, image: str = None) -> None:
        """Adds an image to a page given the url."""
        self.images.append(image)

    @classmethod
    async def paginate(
        cls, pages: list[tuple[str, str]], ctx: ApplicationContext, embed: Embed,
        prefix: str = "", suffix: str = "", restrict_to_user: User = None,
        timeout: int = constants.pagination.timeout, footer_text: str = None, url: str = None,
        exception_on_empty_embed: bool = False
    ) -> None:
        """
        Use a paginator and set of reactions to provide pagination over a set of title/image pairs.

        `pages` is a list of tuples of page title/image url pairs.
        `prefix` and `suffix` will be prepended and appended respectively to the message.
        When used, this will send a message using `ctx.respond()` and apply a set of reactions to it.
        These reactions may be used to change page, or to remove pagination from the message.
        Note: Pagination will be removed automatically if no reaction is added for `timeout` seconds,
              defaulting to five minutes (300 seconds).
        """

        def event_check(reaction_: Reaction, user_: Member) -> bool:
            """Make sure that this reaction is what we want to operate on."""
            no_restrictions = (
                not restrict_to_user  # Pagination is not restricted.
                or user_.id == restrict_to_user.id  # The reaction was by a whitelisted user.
            )

            # Conditions for a successful pagination:
            return all(
                (
                    reaction_.message.id == message.id,  # Reaction is on this message.
                    reaction_.emoji in PAGINATION_EMOJIS,  # Reaction is one of the pagination emotes.
                    user_.id != ctx.bot.user.id,  # Reaction was not made by the Bot.
                    no_restrictions  # There were no restrictions.
                )
            )

        paginator = cls(prefix=prefix, suffix=suffix)
        current_page = 0

        if not pages:
            if exception_on_empty_embed:
                log.exception("Pagination asked for empty image list")
                raise EmptyPaginatorEmbedError("No images to paginate")

            log.debug("No images to add to paginator, adding '(no images to display)' message")
            pages.append(("(no images to display)", ""))

        for text, image_url in pages:
            try:
                paginator.add_line(text)
                paginator.add_image(image_url)
            except Exception:
                log.exception(f"Failed to add line {text} and image {image_url} to paginator")
                raise

        embed.description = paginator.pages[current_page]
        image = paginator.images[current_page]

        if image:
            embed.set_image(url=image)

        if len(paginator.pages) <= 1:
            if footer_text:
                embed.set_footer(text=footer_text)

            if url:
                embed.url = url

            log.debug("There's less than two pages, so we won't paginate - sending single page on its own")
            await ctx.respond(embed=embed)
            return

        if footer_text:
            embed.set_footer(text=f"{footer_text} (Page {current_page + 1}/{len(paginator.pages)})")
        else:
            embed.set_footer(text=f"Page {current_page + 1}/{len(paginator.pages)}")

        if url:
            embed.url = url

        await ctx.respond(embed=embed)
        message = await ctx.interaction.original_message()

        log.debug(f"Paginator created with {len(paginator.pages)} pages (ID: {message.id})")

        for emoji in PAGINATION_EMOJIS:
            await message.add_reaction(emoji)

        while True:
            try:
                reaction, user = await ctx.bot.wait_for("reaction_add", timeout=timeout, check=event_check)
            except asyncio.TimeoutError:
                log.debug(f"Timed out waiting for a reaction (ID: {message.id})")
                break  # We're done, no reactions for the last 5 minutes.

            # Deletes the users reaction.
            await message.remove_reaction(reaction.emoji, user)

            reaction_type = ""
            if reaction.emoji == LOCK_EMOJI:
                log.debug(f"Got lock reaction (ID: {message.id})")
                break

            elif reaction.emoji == FIRST_EMOJI:
                if current_page == 0:
                    log.debug(f"Got first page reaction, but we're on the first page - ignoring (ID: {message.id})")
                    continue

                current_page = 0
                reaction_type = "first"

            elif reaction.emoji == LAST_EMOJI:
                if current_page >= len(paginator.pages) - 1:
                    log.debug(f"Got last page reaction, but we're on the last page - ignoring (ID: {message.id})")
                    continue

                current_page = len(paginator.pages) - 1
                reaction_type = "last"

            elif reaction.emoji == LEFT_EMOJI:
                if current_page <= 0:
                    log.debug(f"Got previous page reaction, but we're on the first page - ignoring (ID: {message.id})")
                    continue

                current_page -= 1
                reaction_type = "previous"

            elif reaction.emoji == RIGHT_EMOJI:
                if current_page >= len(paginator.pages) - 1:
                    log.debug(f"Got next page reaction, but we're on the last page - ignoring (ID: {message.id})")
                    continue

                current_page += 1
                reaction_type = "next"

            # Magic happens here, after page and reaction_type is set.
            embed.description = ""
            await message.edit(embed=embed)
            embed.description = paginator.pages[current_page]

            image = paginator.images[current_page] or Embed.Empty
            embed.set_image(url=image)

            if footer_text:
                embed.set_footer(text=f"{footer_text} (Page {current_page + 1}/{len(paginator.pages)})")
            else:
                embed.set_footer(text=f"Page {current_page + 1}/{len(paginator.pages)}")

            page = f"{current_page + 1}/{len(paginator.pages)}"
            log.debug(f"Got {reaction_type} page reaction - changing to page {page} (ID: {message.id})")

            await message.edit(embed=embed)

        log.debug(f"Ending pagination and clearing reactions... (ID: {message.id})")
        await message.clear_reactions()
