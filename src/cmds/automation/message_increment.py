import logging

from discord import Member, Message, User
from discord.ext import commands
from sqlalchemy import select
from typing import Sequence
from src.bot import Bot
from src.database.models import MessageCount
from src.database.session import AsyncSessionLocal
from src.helpers.verification import get_user_details, process_identification

logger = logging.getLogger(__name__)


class MessageIncrement(commands.Cog):
    """Cog for incrementing message count in the DB for the APT role"""

    def __init__(self, bot: Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, ctx: Message):
        user = ctx.author
        async with AsyncSessionLocal() as session:
            stmt = select(MessageCount).filter(MessageCount.user_id == user.id)
            result = await session.scalars(stmt)
            messages: Sequence[MessageCount] = result.all()
        if not messages:
            session.add(MessageCount(user_id=user.id, MessageCount=1))
        else:
            messages_cnt = messages + 1
            session.update(MessageCount(user_id=user.id, MessageCount=messages_cnt))