# flake8: noqa: D101
from datetime import datetime

from sqlalchemy import Boolean, Integer
from sqlalchemy.dialects.mysql import BIGINT, TEXT, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class Macro(Base):
    """
    Represents a Macro record in the database that allows sending frequently used texts.

    Attributes:
        id (int): The unique ID of the macro record (primary key).
        user_id (int): The ID of the user who created the macro.
        name (str): The name of the macro. Must be unique.
        text (str): The macro itself.
        created_at (datetime): The timestamp when the macro was created.
    """
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BIGINT(18))
    name: Mapped[str] = mapped_column(TEXT, nullable=False, unique=True)
    text: Mapped[str] = mapped_column(TEXT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)
