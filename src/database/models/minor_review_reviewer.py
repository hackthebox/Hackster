# flake8: noqa: D101
from datetime import datetime

from sqlalchemy import Integer
from sqlalchemy.dialects.mysql import BIGINT, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class MinorReviewReviewer(Base):
    """
    Stores Discord user IDs of users allowed to review minor reports.
    Configurable at runtime by Administrators.
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False, unique=True)
    added_by: Mapped[int | None] = mapped_column(BIGINT(18), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
