"""Administrator commands to manage who can review minor reports."""

import logging
from datetime import datetime, timezone

import discord
from discord import ApplicationContext, WebhookMessage
from discord.ext.commands import has_any_role
from sqlalchemy import select

from src.bot import Bot
from src.core import settings
from src.database.models import MinorReviewReviewer
from src.database.session import AsyncSessionLocal
from src.helpers.minor_verification import get_minor_review_reviewer_ids, invalidate_reviewer_ids_cache

logger = logging.getLogger(__name__)


class MinorReviewersCog(discord.Cog):
    """Admin commands to add/remove/list minor report reviewers."""

    def __init__(self, bot: Bot):
        self.bot = bot

    minor_reviewers = discord.SlashCommandGroup(
        "minor_reviewers",
        "Manage who can review minor reports (Administrators only).",
        guild_ids=settings.guild_ids,
    )

    @minor_reviewers.command(description="Add a user as a minor report reviewer.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"))
    async def add(
        self,
        ctx: ApplicationContext,
        user: discord.Member,
    ) -> ApplicationContext | WebhookMessage:
        """Add a user to the list of reviewers."""
        uid = user.id
        async with AsyncSessionLocal() as session:
            stmt = select(MinorReviewReviewer).filter(MinorReviewReviewer.user_id == uid).limit(1)
            result = await session.scalars(stmt)
            existing = result.first()
            if existing:
                return await ctx.respond(
                    f"{user.mention} is already a minor report reviewer.",
                    ephemeral=True,
                )
            now = datetime.now(timezone.utc)
            session.add(
                MinorReviewReviewer(
                    user_id=uid,
                    added_by=ctx.user.id,
                    created_at=now,
                )
            )
            await session.commit()
        invalidate_reviewer_ids_cache()
        return await ctx.respond(
            f"Added {user.mention} as a minor report reviewer.",
            ephemeral=True,
        )

    @minor_reviewers.command(description="Remove a user from minor report reviewers.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"))
    async def remove(
        self,
        ctx: ApplicationContext,
        user: discord.Member,
    ) -> ApplicationContext | WebhookMessage:
        """Remove a user from the list of reviewers."""
        uid = user.id
        async with AsyncSessionLocal() as session:
            stmt = select(MinorReviewReviewer).filter(MinorReviewReviewer.user_id == uid).limit(1)
            result = await session.scalars(stmt)
            row = result.first()
            if not row:
                return await ctx.respond(
                    f"{user.mention} is not in the minor report reviewer list.",
                    ephemeral=True,
                )
            await session.delete(row)
            await session.commit()
        invalidate_reviewer_ids_cache()
        return await ctx.respond(
            f"Removed {user.mention} from minor report reviewers.",
            ephemeral=True,
        )

    @minor_reviewers.command(name="list", description="List users who can review minor reports.")
    @has_any_role(*settings.role_groups.get("ALL_ADMINS"))
    async def list_reviewers(self, ctx: ApplicationContext) -> ApplicationContext | WebhookMessage:
        """List current minor report reviewers."""
        ids = await get_minor_review_reviewer_ids()
        if not ids:
            return await ctx.respond(
                "There are no minor report reviewers configured. Add some with `/minor_reviewers add`.",
                ephemeral=True,
            )
        lines = [f"<@{uid}> ({uid})" for uid in ids]
        return await ctx.respond(
            "**Minor report reviewers:**\n" + "\n".join(lines),
            ephemeral=True,
        )


def setup(bot: Bot) -> None:
    """Load the MinorReviewersCog."""
    bot.add_cog(MinorReviewersCog(bot))
