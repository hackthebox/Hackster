# flake8: noqa: D101
from datetime import datetime

from sqlalchemy import Boolean, Integer
from sqlalchemy.dialects.mysql import BIGINT, TEXT, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Ban(Base):
    """
    Represents a Ban record in the database.

    Attributes:
        id (int): The unique ID of the ban record (primary key).
        user_id (int): The ID of the user who has been banned.
        reason (str): The reason for the ban, cannot be null.
        moderator_id (int): The ID of the moderator who issued the ban, cannot be null.
        unban_time (int): The time when the user will be unbanned (nullable).
        approved (bool): Whether the ban has been approved or not, cannot be null.
        unbanned (bool): Whether the user has been unbanned or not, cannot be null, default is False.
        timestamp (datetime): The timestamp when the ban was issued, cannot be null.
    """
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(18))
    reason: Mapped[str] = mapped_column(TEXT, nullable=False)
    moderator_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    unban_time: Mapped[int] = mapped_column(Integer)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    unbanned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timestamp: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
