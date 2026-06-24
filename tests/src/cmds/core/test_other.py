from unittest.mock import AsyncMock, patch

import pytest
from discord import ApplicationContext

from src.bot import Bot
from src.cmds.core import other
from src.cmds.core.other import OtherCog, SpoilerModal
from src.core import settings
from src.helpers import feedback_service, webhook


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

        assert content == "https://help.hackthebox.com/en/articles/13645526-contacting-academy-support"

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



    @pytest.mark.asyncio
    async def test_feedback_modal_sends_to_feedback_service(self):
        """Test the feedback modal posts structured payload to the feedback service."""
        modal = other.FeedbackModal(
            title="HTB Feedback",
            kind="suggestion",
            platform="htb_discord",
        )
        interaction = AsyncMock()
        interaction.id = 999888777
        interaction.user.id = 123456789012345678
        interaction.user.name = "TestUser"
        interaction.guild = None
        for child in modal.children:
            if child.custom_id == "summary":
                child.value = "Badge precedence"
            elif child.custom_id == "details":
                child.value = "CWPE should override CPTS badge in Discord"
            elif child.custom_id == "product":
                child.value = "certifications"

        with (
            patch.object(modal, "_lookup_htb_user_id", new_callable=AsyncMock, return_value="42"),
            patch.object(feedback_service, "is_configured", return_value=True),
            patch.object(feedback_service, "ingest_discord_feedback", new_callable=AsyncMock, return_value=True) as mock_ingest,
            patch("src.cmds.core.other.WebhookClient") as mock_slack_client,
        ):
            mock_slack_client.return_value.send.return_value.status_code = 200
            mock_slack_client.return_value.send.return_value.body = "ok"

            await modal.callback(interaction)

            interaction.response.send_message.assert_called_once_with(
                "Thank you, your feedback has been recorded.",
                ephemeral=True,
            )
            mock_ingest.assert_called_once_with(
                {
                    "external_id": "999888777",
                    "title": "Badge precedence",
                    "body": "CWPE should override CPTS badge in Discord",
                    "kind": "suggestion",
                    "platform": "htb_discord",
                    "product": "certifications",
                    "author_source_user_id": "123456789012345678",
                    "submitted_at": mock_ingest.call_args[0][0]["submitted_at"],
                    "author_htb_user_id": "42",
                }
            )

    @pytest.mark.asyncio
    async def test_feedback_modal_falls_back_to_slack_when_feedback_service_unconfigured(self):
        """Test legacy Slack path when feedback service URL/key are unset."""
        modal = other.FeedbackModal(title="HTB Feedback", kind="bug", platform="htb_labs")
        interaction = AsyncMock()
        interaction.id = 111
        interaction.user = None
        for child in modal.children:
            if child.custom_id == "summary":
                child.value = "Title"
            elif child.custom_id == "details":
                child.value = "Body"

        with (
            patch.object(feedback_service, "is_configured", return_value=False),
            patch.object(feedback_service, "ingest_discord_feedback", new_callable=AsyncMock) as mock_ingest,
            patch("src.cmds.core.other.WebhookClient") as mock_slack_client,
        ):
            mock_slack_client.return_value.send.return_value.status_code = 200
            mock_slack_client.return_value.send.return_value.body = "ok"

            await modal.callback(interaction)

            mock_ingest.assert_not_called()
            mock_slack_client.return_value.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_feedback_modal_falls_back_to_slack_when_feedback_service_fails(self):
        """Test Slack fallback when feedback service is configured but ingest fails."""
        modal = other.FeedbackModal(title="HTB Feedback", kind="bug", platform="htb_labs")
        interaction = AsyncMock()
        interaction.id = 222
        interaction.user.id = 123456789012345678
        interaction.user.name = "TestUser"
        interaction.guild = None
        for child in modal.children:
            if child.custom_id == "summary":
                child.value = "Title"
            elif child.custom_id == "details":
                child.value = "Body"

        with (
            patch.object(modal, "_lookup_htb_user_id", new_callable=AsyncMock, return_value=""),
            patch.object(feedback_service, "is_configured", return_value=True),
            patch.object(feedback_service, "ingest_discord_feedback", new_callable=AsyncMock, return_value=False),
            patch("src.cmds.core.other.WebhookClient") as mock_slack_client,
        ):
            mock_slack_client.return_value.send.return_value.status_code = 200
            mock_slack_client.return_value.send.return_value.body = "ok"

            await modal.callback(interaction)

            mock_slack_client.return_value.send.assert_called_once()

    def test_setup(self, bot):
        """Test the setup method of the cog."""
        # Invoke the command
        other.setup(bot)

        bot.add_cog.assert_called_once()
