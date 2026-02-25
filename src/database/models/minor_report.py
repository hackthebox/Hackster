# flake8: noqa: D101
from datetime import datetime

from sqlalchemy import Integer
from sqlalchemy.dialects.mysql import BIGINT, TEXT, TIMESTAMP, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class MinorReport(Base):
    """
    Represents a minor flag report for review by select moderators.

    Attributes:
        id: Primary key.
        user_id: Discord user ID of the reported user.
        reporter_id: Discord user ID of the moderator who flagged.
        suspected_age: Suspected age (1-17).
        evidence: Evidence for the flag.
        report_message_id: Discord message ID in the review channel.
        status: pending, approved, denied, consent_verified.
        reviewer_id: Discord user ID of moderator who approved/denied (nullable).
        created_at: When the report was created.
        updated_at: When the report was last updated.
        associated_ban_id: Ban record ID if user was banned via this report (nullable).
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    reporter_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    suspected_age: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence: Mapped[str] = mapped_column(TEXT, nullable=False)
    report_message_id: Mapped[int] = mapped_column(BIGINT(20), nullable=False)
    status: Mapped[str] = mapped_column(VARCHAR(32), nullable=False, default="pending")
    reviewer_id: Mapped[int | None] = mapped_column(BIGINT(18), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    associated_ban_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
