# flake8: noqa: D101
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, TEXT, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from . import Base


class AnonymousVoteSession(Base):
    """Timed anonymous vote session over one or more nominees."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    channel_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    message_id: Mapped[int | None] = mapped_column(BIGINT(18), nullable=True)
    topic: Mapped[str | None] = mapped_column(TEXT, nullable=True)
    created_by_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    candidates: Mapped[list["AnonymousVoteCandidate"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )
    ballots: Mapped[list["AnonymousVoteBallot"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class AnonymousVoteCandidate(Base):
    """A nominee in an anonymous vote session."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("anonymous_vote_session.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    display_name: Mapped[str] = mapped_column(TEXT, nullable=False)

    session: Mapped["AnonymousVoteSession"] = relationship(back_populates="candidates")
    ballots: Mapped[list["AnonymousVoteBallot"]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )


class AnonymousVoteBallot(Base):
    """A single voter's choice for one nominee. voter_id is never shown in Discord."""

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "candidate_id",
            "voter_id",
            name="uq_anonymous_vote_ballot_session_candidate_voter",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("anonymous_vote_session.id", ondelete="CASCADE"), nullable=False
    )
    candidate_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("anonymous_vote_candidate.id", ondelete="CASCADE"), nullable=False
    )
    voter_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    choice: Mapped[str] = mapped_column(String(16), nullable=False)

    session: Mapped["AnonymousVoteSession"] = relationship(back_populates="ballots")
    candidate: Mapped["AnonymousVoteCandidate"] = relationship(back_populates="ballots")
