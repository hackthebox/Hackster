import logging

import discord
from discord import ApplicationContext, Embed, Interaction, Message, WebhookMessage, slash_command
from discord.ext import commands
from discord.ui import InputText, Modal
from slack_sdk.webhook import WebhookClient

from src.bot import Bot
from src.core import settings

logger = logging.getLogger(__name__)


class FeedbackModal(Modal):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.add_item(InputText(label="Title"))
        self.add_item(InputText(label="Feedback", style=discord.InputTextStyle.long))

    async def callback(self, interaction: discord.Interaction):
        
        await interaction.response.send_message("Thank you, your feedback has been recorded.", ephemeral=True)

        webhook = WebhookClient(settings.SLACK_WEBHOOK) # Establish Slack Webhook
        
        if interaction.user: # Protects against some weird edge-cases
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


class OtherCog(commands.Cog):
    """Ban related commands."""

    def __init__(self, bot: Bot):
        self.bot = bot

    @slash_command(guild_ids=settings.guild_ids, description="A simple reply stating hints are not allowed.")
    async def no_hints(
            self, ctx: ApplicationContext
    ) -> Message:
        """A simple reply stating hints are not allowed."""
        return await ctx.respond(
            "No hints are allowed for the duration the event is going on. This is a competitive event with prizes. "
            "Once the event is over you are more then welcome to share solutions/write-ups/etc and try them in the "
            "After Party event."
        )

    @slash_command(guild_ids=settings.guild_ids,
                   description="A simple reply proving a link to the support desk article on how to get support")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def support(
            self, ctx: ApplicationContext
    ) -> Message:
        """A simple reply proving a link to the support desk article on how to get support"""
        return await ctx.respond(
            "https://help.hackthebox.com/en/articles/5986762-contacting-htb-support"
        )

    @slash_command(guild_ids=settings.guild_ids, description="Add the URL which has spoiler link.")
    async def spoiler(self, ctx: ApplicationContext, url: str) -> Interaction | WebhookMessage:
        """Add the URL which has spoiler link."""
        if len(url) == 0:
            return await ctx.respond("Please provide the spoiler URL.")

        embed = Embed(title="Spoiler Report", color=0xB98700)
        embed.add_field(name=f"{ctx.user} has submitted a spoiler.", value=f"URL: <{url}>", inline=False)

        channel = self.bot.get_channel(settings.channels.SPOILER)
        await channel.send(embed=embed)
        return await ctx.respond("Thanks for the reporting the spoiler.", ephemeral=True, delete_after=15)

    @slash_command(guild_ids=settings.guild_ids, description="Provide feedback to HTB!")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def feedback(self, ctx: ApplicationContext) -> Interaction:
        """ Provide Feedback to HTB  """
        # Send the Modal defined above in Feedback Modal, which handles the callback
        modal = FeedbackModal(title="Feedback")
        return await ctx.send_modal(modal)


def setup(bot: Bot) -> None:
    """Load the `ChannelManageCog` cog."""
    bot.add_cog(OtherCog(bot))
