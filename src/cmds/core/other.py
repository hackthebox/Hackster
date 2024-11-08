import logging

import discord
from discord import ApplicationContext, Interaction, Message, WebhookMessage, slash_command
from discord.ext import commands
from discord.ui import InputText, Modal
from slack_sdk.webhook import WebhookClient

from src.bot import Bot
from src.core import settings

logger = logging.getLogger(__name__)


class FeedbackModal(Modal):
    """Modal for collecting user feedback."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the Feedback Modal with input fields."""
        super().__init__(*args, **kwargs)
        self.add_item(InputText(label="Title"))
        self.add_item(InputText(label="Feedback", style=discord.InputTextStyle.long))

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the modal submission by sending feedback to Slack."""
        await interaction.response.send_message("Thank you, your feedback has been recorded.", ephemeral=True)

        webhook = WebhookClient(settings.SLACK_WEBHOOK)

        if interaction.user:
            title = f"{self.children[0].value} - {interaction.user.name}"
        else:
            title = self.children[0].value

        message_body = self.children[1].value
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

    @slash_command(guild_ids=settings.guild_ids, description="Link to the support desk article.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def support(self, ctx: ApplicationContext) -> Message:
        """Provide a link to the support desk article."""
        return await ctx.respond("https://help.hackthebox.com/en/articles/5986762-contacting-htb-support")

    @slash_command(guild_ids=settings.guild_ids, description="Add a URL which contains a spoiler.")
    async def spoiler(self, ctx: ApplicationContext, url: str) -> Interaction | WebhookMessage:
        """Add a URL that contains a spoiler."""
        if not url:
            return await ctx.respond("Please provide the spoiler URL.")

        user_name = ctx.user.display_name

        webhook = WebhookClient(settings.SLACK_LEAKS_WEBHOOK)

        try:
            response = webhook.send(
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": f"{user_name} has submitted a Spoiler Report",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "plain_text",
                            "text": f"Reported URL: {url}",
                            "emoji": True
                        }
                    }
                ]
            )

            if response.status_code != 200:
                print(f"Failed to send to Slack: {response.status_code} - {response.body}")
        except Exception as e:
            print(f"Error sending to Slack: {e}")

        return await ctx.respond("Thanks for reporting the spoiler.", ephemeral=True, delete_after=15)

    @slash_command(guild_ids=settings.guild_ids, description="Provide feedback to HTB.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def feedback(self, ctx: ApplicationContext) -> Interaction:
        """Provide feedback to HTB."""
        modal = FeedbackModal(title="Feedback")
        return await ctx.send_modal(modal)


def setup(bot: Bot) -> None:
    """Load the OtherCog cog."""
    bot.add_cog(OtherCog(bot))
