# flake8: noqa: D101
from datetime import date

from sqlalchemy import Integer, func
from sqlalchemy.dialects.mysql import BIGINT, DATE, TEXT
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Infraction(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    reason = mapped_column(TEXT, nullable=False)
    weight: Mapped[int] = mapped_column(Integer, nullable=False)
    moderator_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    date: Mapped[date] = mapped_column(DATE, nullable=False, server_default=func.curdate())
