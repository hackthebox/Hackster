from unittest.mock import AsyncMock, patch

import pytest
from discord import ApplicationContext

from src.bot import Bot
from src.cmds.core import other
from src.cmds.core.other import OtherCog, SpoilerModal
from src.core import settings
from src.helpers import webhook


class TestWebhookHelper:
    """Test the webhook helper functions."""

    @pytest.mark.asyncio
    async def test_webhook_call_success(self):
        """Test successful webhook call."""
        test_url = "http://test.webhook.url"
        test_data = {"key": "value"}

        # Mock the aiohttp ClientSession
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_post.return_value.__aenter__.return_value = mock_response

            await webhook.webhook_call(test_url, test_data)

            # Verify the post was called with correct parameters
            mock_post.assert_called_once_with(test_url, json=test_data)

    @pytest.mark.asyncio
    async def test_webhook_call_failure(self):
        """Test failed webhook call."""
        test_url = "http://test.webhook.url"
        test_data = {"key": "value"}

        # Mock the aiohttp ClientSession
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 500
            mock_response.text = AsyncMock(return_value="Internal Server Error")
            mock_post.return_value.__aenter__.return_value = mock_response

            # Test should complete without raising an exception
            await webhook.webhook_call(test_url, test_data)


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
        """Test the spoiler modal callback with a valid URL."""
        modal = SpoilerModal(title="Report Spoiler")
        interaction = AsyncMock()
        interaction.user.display_name = "TestUser"
        modal.children[0].value = "Test description"
        modal.children[1].value = "http://example.com/spoiler"

        with patch('src.helpers.webhook.webhook_call', new_callable=AsyncMock) as mock_webhook:
            await modal.callback(interaction)

            interaction.response.send_message.assert_called_once_with(
                "Thank you, the spoiler has been reported.", ephemeral=True
            )

            # Verify webhook was called with correct data
            mock_webhook.assert_called_once_with(
                settings.JIRA_WEBHOOK,
                {
                    "user": "TestUser",
                    "url": "http://example.com/spoiler",
                    "desc": "Test description",
                    "type": "spoiler"
                }
            )

    @pytest.mark.asyncio
    async def test_cheater_command(self, bot, ctx):
        """Test the cheater command with valid inputs."""
        cog = OtherCog(bot)
        ctx.bot = bot
        ctx.user.display_name = "ReporterUser"

        test_username = "SuspectedUser"
        test_description = "Suspicious activity description"

        with patch('src.helpers.webhook.webhook_call', new_callable=AsyncMock) as mock_webhook:
            await cog.cheater.callback(cog, ctx, test_username, test_description)

            # Verify the webhook was called with correct data
            mock_webhook.assert_called_once_with(
                settings.JIRA_WEBHOOK,
                {
                    "user": "ReporterUser",
                    "cheater": test_username,
                    "description": test_description,
                    "type": "cheater"
                }
            )

            # Verify the response was sent
            ctx.respond.assert_called_once_with(
                "Thank you for your report.",
                ephemeral=True
            )



    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        other.setup(bot)

        bot.add_cog.assert_called_once()
