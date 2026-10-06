# flake8: noqa: D101
from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT, TEXT
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
    closes_at: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Set once the results are posted. closed without published_at means the post failed or the
    # bot stopped first; register_anonymous_vote_views retries those.
    published_at: Mapped[int | None] = mapped_column(BIGINT(18), nullable=True)

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
    """
    A single voter's choice for one nominee.

    The voter is stored as HMAC(VOTE_HMAC_SECRET, "<session_id>:<voter_id>"), never as a Discord id,
    so the database or a backup alone cannot tell who voted which way. Anyone who also holds the
    secret can still recover it by hashing each eligible voter's id.
    """

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "candidate_id",
            "voter_hash",
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
    voter_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    choice: Mapped[str] = mapped_column(String(16), nullable=False)

    session: Mapped["AnonymousVoteSession"] = relationship(back_populates="ballots")
    candidate: Mapped["AnonymousVoteCandidate"] = relationship(back_populates="ballots")
