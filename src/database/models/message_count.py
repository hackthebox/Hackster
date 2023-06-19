# flake8: noqa: D101

from sqlalchemy import Integer
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class MessageCount(Base):
    """
    Represents a Message Count record in the Database.

    Attributes:
        user_id (int): The ID of the user who has been banned.
        message_count(int): Message Count of User
    """
    user_id: Mapped[int] = mapped_column(BIGINT(18), primary_key=True)
    message_count: Mapped[int] = mapped_column(Integer)