import logging

import aiohttp
import discord
from discord import ApplicationContext, Interaction, Message, Option, slash_command
from discord.ext import commands
from discord.ui import InputText, Modal
from slack_sdk.webhook import WebhookClient

from src.bot import Bot
from src.core import settings

logger = logging.getLogger(__name__)


class FeedbackModal(Modal):
    """Feedback modal."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the Feedback Modal with input fields."""
        super().__init__(*args, **kwargs)
        self.add_item(InputText(label="Title"))
        self.add_item(InputText(label="Feedback", style=discord.InputTextStyle.long))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the modal submission by sending feedback to Slack."""
        await interaction.response.send_message("Thank you, your feedback has been recorded.", ephemeral=True)

        webhook = WebhookClient(settings.SLACK_FEEDBACK_WEBHOOK)

        if interaction.user:  # Protects against some weird edge-cases
            title = f"{self.children[0].value} - {interaction.user.name}"
        else:
            title = f"{self.children[0].value}"

        message_body = self.children[1].value
        # Slack has no way to disallow @(@everyone calls), so we strip it out and replace it with a safe version
        title = title.replace("@", "[at]").replace("<", "[bracket]")
        message_body = message_body.replace("@", "[at]").replace("<", "[bracket]")

        response = webhook.send(
            text=f"{title} - {message_body}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{title}:\n {message_body}"
                    }
                }
            ]
        )
        assert response.status_code == 200
        assert response.body == "ok"


class SpoilerModal(Modal):
    """Modal for reporting a spoiler."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the Spoiler Modal with input fields."""
        super().__init__(*args, **kwargs)
        self.add_item(InputText(label="Description", placeholder="Description", style=discord.InputTextStyle.long))
        self.add_item(InputText(label="URL", placeholder="Enter URL", required=True, style=discord.InputTextStyle.long))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the modal submission by sending the spoiler report to JIRA."""
        desc = self.children[0].value.strip()  # Trim any whitespace
        url = self.children[1].value.strip()  # Trim any whitespace

        if not url:  # Check if the URL is empty
            await interaction.response.send_message("Please provide the spoiler URL.", ephemeral=True)
            return
        await interaction.response.send_message("Thank you, the spoiler has been reported.", ephemeral=True)

        user_name = interaction.user.display_name

        webhook_url = settings.JIRA_SPOILER_WEBHOOK

        payload = {
            "user": user_name,
            "desc": desc,
            "url": url,
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(webhook_url, json=payload) as response:
                    if response.status != 200:
                        logger.error(f"Failed to send to JIRA: {response.status} - {await response.text()}")
            except Exception as e:
                logger.error(f"Error sending to JIRA: {e}")


class OtherCog(commands.Cog):
    """Other commands related to the bot."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @slash_command(guild_ids=settings.guild_ids, description="A simple reply stating hints are not allowed.")
    async def no_hints(self, ctx: ApplicationContext) -> Message:
        """Reply stating that hints are not allowed."""
        return await ctx.respond(
            "No hints are allowed for the duration of the event. Once the event is over, feel free to share solutions."
        )

    @slash_command(guild_ids=settings.guild_ids,
                   description="A simple reply proving a link to the support desk article on how to get support")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def support(
            self, ctx: ApplicationContext,
            platform: Option(str, "Select the platform", choices=["labs", "academy"], default="labs"),
    ) -> Message:
        """A simple reply providing a link to the support desk article on how to get support."""
        if platform == "academy":
            return await ctx.respond(
                "https://help.hackthebox.com/en/articles/5987511-contacting-academy-support"
            )
        return await ctx.respond(
            "https://help.hackthebox.com/en/articles/5986762-contacting-htb-support"
        )

    @slash_command(guild_ids=settings.guild_ids, description="Add a URL which contains a spoiler.")
    async def spoiler(self, ctx: ApplicationContext) -> Interaction:
        """Report a URL that contains a spoiler."""
        modal = SpoilerModal(title="Report Spoiler")
        return await ctx.send_modal(modal)

    @slash_command(guild_ids=settings.guild_ids, description="Provide feedback to HTB.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def feedback(self, ctx: ApplicationContext) -> Interaction:
        """Provide feedback to HTB."""
        modal = FeedbackModal(title="Feedback")
        return await ctx.send_modal(modal)


def setup(bot: Bot) -> None:
    """Load the OtherCog cog."""
    bot.add_cog(OtherCog(bot))
