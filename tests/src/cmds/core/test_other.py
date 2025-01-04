from unittest.mock import AsyncMock, patch

import pytest
from discord import ApplicationContext

from src.bot import Bot
from src.cmds.core import other
from src.cmds.core.other import OtherCog, SpoilerModal
from src.core import settings


class TestOther:
    """Test the `ChannelManage` cog."""

    @pytest.mark.asyncio
    async def test_no_hints(self, bot, ctx):
        """Test the response of the `no_hints` command."""
        cog = OtherCog(bot)
        ctx.bot = bot

        # Invoke the command.
        await cog.no_hints.callback(cog, ctx)

        args, kwargs = ctx.respond.call_args
        content = args[0]

        # Command should respond with a string.
        assert isinstance(content, str)

        assert content.startswith("No hints are allowed")

    @pytest.mark.asyncio
    async def test_support_labs(self, bot, ctx):
        """Test the response of the `support` command."""
        cog = other.OtherCog(bot)
        ctx.bot = bot
        platform = "labs"

        # Invoke the command.
        await cog.support.callback(cog, ctx, platform)

        args, kwargs = ctx.respond.call_args
        content = args[0]

        # Command should respond with a string.
        assert isinstance(content, str)

        assert content == "https://help.hackthebox.com/en/articles/5986762-contacting-htb-support"

    @pytest.mark.asyncio
    async def test_support_academy(self, bot, ctx):
        """Test the response of the `support` command."""
        cog = other.OtherCog(bot)
        ctx.bot = bot
        platform = "academy"

        # Invoke the command.
        await cog.support.callback(cog, ctx, platform)

        args, kwargs = ctx.respond.call_args
        content = args[0]

        # Command should respond with a string.
        assert isinstance(content, str)

        assert content == "https://help.hackthebox.com/en/articles/5987511-contacting-academy-support"

    @pytest.mark.asyncio
    async def test_support_urls_different(self, bot, ctx):
        """Test that the URLs for 'labs' and 'academy' platforms are different."""
        cog = other.OtherCog(bot)
        ctx.bot = bot

        # Test the 'labs' platform
        await cog.support.callback(cog, ctx, "labs")
        labs_url = ctx.respond.call_args[0][0]

        # Test the 'academy' platform
        await cog.support.callback(cog, ctx, "academy")
        academy_url = ctx.respond.call_args[0][0]

        # Assert that the URLs are different
        assert labs_url != academy_url

    @pytest.mark.asyncio
    async def test_spoiler_modal_callback_with_url(self):
        modal = SpoilerModal(title="Report Spoiler")
        interaction = AsyncMock()
        interaction.user.display_name = "TestUser"
        modal.children[0].value = "Test description"
        modal.children[1].value = "http://example.com/spoiler"

        with patch('aiohttp.ClientSession.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value.__aenter__.return_value.status = 200
            await modal.callback(interaction)
            interaction.response.send_message.assert_called_once_with(
                "Thank you, the spoiler has been reported.", ephemeral=True
            )
            await mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_spoiler_modal_callback_with_url(self):
        modal = SpoilerModal(title="Report Spoiler")
        interaction = AsyncMock()
        interaction.user.display_name = "TestUser"
        modal.children[0].value = "Test description"
        modal.children[1].value = "http://example.com/spoiler"

        with patch('aiohttp.ClientSession.post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value.__aenter__.return_value.status = 200
            await modal.callback(interaction)
            interaction.response.send_message.assert_called_once_with(
                "Thank you, the spoiler has been reported.", ephemeral=True
            )
            mock_post.assert_called_once()

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        other.setup(bot)

        bot.add_cog.assert_called_once()
