# flake8: noqa: D101
from sqlalchemy import Integer
from sqlalchemy.dialects.mysql import BIGINT, TEXT
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Mute(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    reason: Mapped[str] = mapped_column(TEXT, nullable=False)
    moderator_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    unmute_time: Mapped[int] = mapped_column(BIGINT(11, unsigned=True), nullable=False)
