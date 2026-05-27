import logging
from datetime import UTC, datetime

import discord
from discord import ApplicationContext, Interaction, Message, Option, slash_command
from discord.ext import commands
from discord.ui import Button, InputText, Modal, View
from slack_sdk.webhook import WebhookClient
from sqlalchemy import select

from src.bot import Bot
from src.constants.feedback import feedback_kind_choices, feedback_platform_choices
from src.core import settings
from src.database.models import HtbDiscordLink
from src.database.session import AsyncSessionLocal
from src.helpers import feedback_service, webhook

logger = logging.getLogger(__name__)


def _sanitize_feedback_text(text: str) -> str:
    """Strip characters that could trigger Slack @-mentions."""
    return text.replace("@", "[at]").replace("<", "[bracket]")


def _modal_field_value(modal: Modal, custom_id: str) -> str:
    for child in modal.children:
        if getattr(child, "custom_id", None) == custom_id:
            return (child.value or "").strip()
    return ""


class FeedbackModal(Modal):
    """Collect structured feedback for the feedback service."""

    def __init__(self, *, kind: str, platform: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.kind = kind
        self.platform = platform
        self.add_item(
            InputText(
                label="Summary",
                custom_id="summary",
                placeholder="Brief summary (e.g. VPN drops during Pro Labs)",
                max_length=150,
                required=True,
            )
        )
        self.add_item(
            InputText(
                label="Details",
                custom_id="details",
                placeholder="What happened? Steps to reproduce, expected vs actual behavior…",
                style=discord.InputTextStyle.long,
                max_length=4000,
                required=True,
            )
        )
        self.add_item(
            InputText(
                label="Product area (optional)",
                custom_id="product",
                placeholder="e.g. machines, modules, VPN, certifications",
                max_length=100,
                required=False,
            )
        )

    async def _lookup_htb_user_id(self, discord_user_id: int) -> str:
        async with AsyncSessionLocal() as session:
            stmt = select(HtbDiscordLink).filter(
                HtbDiscordLink.discord_user_id == discord_user_id
            ).limit(1)
            result = await session.scalars(stmt)
            link = result.first()
        if link:
            return str(link.htb_user_id)
        return ""

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the modal submission — forward to feedback or legacy Slack."""
        await interaction.response.send_message("Thank you, your feedback has been recorded.", ephemeral=True)

        summary = _modal_field_value(self, "summary")
        details = _modal_field_value(self, "details")
        product = _modal_field_value(self, "product")

        if interaction.user:
            author_source_user_id = str(interaction.user.id)
            author_htb_user_id = await self._lookup_htb_user_id(interaction.user.id)
            slack_title = f"{summary} - {interaction.user.name}"
        else:
            author_source_user_id = ""
            author_htb_user_id = ""
            slack_title = summary

        if feedback_service.is_configured():
            payload: dict[str, str] = {
                "external_id": str(interaction.id),
                "title": summary,
                "body": details,
                "kind": self.kind,
                "platform": self.platform,
                "author_source_user_id": author_source_user_id,
                "submitted_at": datetime.now(UTC).isoformat(),
            }
            if product:
                payload["product"] = product
            if author_htb_user_id:
                payload["author_htb_user_id"] = author_htb_user_id
            if interaction.guild:
                payload["source_label"] = interaction.guild.name
            await feedback_service.ingest_discord_feedback(payload)
            return

        if not settings.SLACK_FEEDBACK_WEBHOOK:
            logger.warning(
                "No feedback destination configured (FEEDBACK_SERVICE_* or SLACK_FEEDBACK_WEBHOOK)"
            )
            return

        kind_label = self.kind.replace("_", " ")
        platform_label = self.platform.replace("htb_", "").replace("_", " ")
        slack_header = f"[{kind_label} / {platform_label}]"
        if product:
            slack_header += f" ({product})"

        title = _sanitize_feedback_text(f"{slack_header} {slack_title}")
        message_body = _sanitize_feedback_text(details)
        slack_webhook = WebhookClient(settings.SLACK_FEEDBACK_WEBHOOK)
        response = slack_webhook.send(
            text=f"{title} - {message_body}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{title}:\n {message_body}",
                    },
                }
            ],
        )
        assert response.status_code == 200
        assert response.body == "ok"


class SpoilerModal(Modal):
    """Modal for reporting a spoiler."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize the Spoiler Modal with input fields."""
        super().__init__(*args, **kwargs)
        self.add_item(
            InputText(
                label="Description",
                placeholder="Description",
                required=False,
                style=discord.InputTextStyle.long
            )
        )
        self.add_item(
            InputText(
                label="URL",
                placeholder="Enter URL. Submitting malicious or fake links will result in consequences.",
                required=True,
                style=discord.InputTextStyle.paragraph
            )
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle the modal submission by sending the spoiler report to JIRA."""
        desc = self.children[0].value.strip()  # Trim any whitespace
        url = self.children[1].value.strip()  # Trim any whitespace

        if not url:  # Check if the URL is empty
            await interaction.response.send_message("Please provide the spoiler URL.", ephemeral=True)
            return
        await interaction.response.send_message("Thank you, the spoiler has been reported.", ephemeral=True)

        user_name = interaction.user.display_name
        webhook_url = settings.JIRA_WEBHOOK

        data = {
            "user": user_name,
            "url": url,
            "desc": desc,
            "type": "spoiler"
        }

        await webhook.webhook_call(webhook_url, data)


class SpoilerConfirmationView(View):
    """A confirmation view before opening the SpoilerModal."""

    def __init__(self, user: discord.Member):
        super().__init__(timeout=60)
        self.user = user

    @discord.ui.button(label="Proceed", style=discord.ButtonStyle.danger)
    async def proceed(self, button: Button, interaction: discord.Interaction) -> None:
        """Opens the spoiler modal after confirmation."""
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This confirmation is not for you.", ephemeral=True)
            return

        modal = SpoilerModal(title="Report Spoiler")
        await interaction.response.send_modal(modal)
        self.stop()


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
                "https://help.hackthebox.com/en/articles/13645526-contacting-academy-support"
            )
        return await ctx.respond(
            "https://help.hackthebox.com/en/articles/5986762-contacting-htb-support"
        )

    @slash_command(guild_ids=settings.guild_ids, description="Add a URL which contains a spoiler.")
    async def spoiler(self, ctx: ApplicationContext) -> None:
        """Ask for confirmation before reporting a spoiler."""
        view = SpoilerConfirmationView(ctx.user)
        await ctx.respond(
            "Thank you for taking the time to report a spoiler. \n ⚠️ **Warning:** Submitting malicious or fake links will result in consequences.",
            view=view,
            ephemeral=True
        )

    @slash_command(guild_ids=settings.guild_ids, description="Provide feedback to HTB.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def feedback(
        self,
        ctx: ApplicationContext,
        kind: Option(
            str,
            "Type of feedback",
            choices=feedback_kind_choices(),
            required=True,
        ),
        platform: Option(
            str,
            "HTB platform this relates to",
            choices=feedback_platform_choices(),
            required=True,
        ),
    ) -> Interaction:
        """Provide structured feedback to HTB."""
        modal = FeedbackModal(title="HTB Feedback", kind=kind, platform=platform)
        return await ctx.send_modal(modal)

    @slash_command(guild_ids=settings.guild_ids, description="Report a suspected cheater on the main platform.")
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def cheater(
        self,
        ctx: ApplicationContext,
        user: Option(str, "Please provide the HTB username.", required=True),
        description: Option(str, "What do you want to report?", required=True),
    ) -> None:
        """Report a suspected cheater on the main platform."""
        data = {
            "user": ctx.user.display_name,
            "cheater": user,
            "description": description,
            "type": "cheater"
        }

        await webhook.webhook_call(settings.JIRA_WEBHOOK, data)

        await ctx.respond("Thank you for your report.", ephemeral=True)


def setup(bot: Bot) -> None:
    """Load the cogs."""
    bot.add_cog(OtherCog(bot))
