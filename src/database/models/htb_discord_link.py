# flake8: noqa: D101
from sqlalchemy import VARCHAR, Integer
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class HtbDiscordLink(Base):
    """
    An SQLAlchemy database model representing the link between a Hack The Box (HTB) user and a Discord user.

    Attributes:
        id (Integer): The primary key for the table.
        account_identifier (VARCHAR): A unique identifier for the account.
        discord_user_id (BIGINT): The Discord user ID (18 digits) associated with the HTB user.
        htb_user_id (BIGINT): The Hack The Box user ID associated with the Discord user.
    """
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_identifier: Mapped[str] = mapped_column(VARCHAR(255))
    discord_user_id: Mapped[int] = mapped_column(BIGINT(18))
    htb_user_id: Mapped[int] = mapped_column(BIGINT)

    @property
    def discord_user_id_as_int(self) -> int:
        """
        Retrieve the discord_user_id as an integer.

        Returns:
            int: The Discord user ID as an integer.
        """
        return int(self.discord_user_id)

    @property
    def htb_user_id_as_int(self) -> int:
        """
        Retrieve the htb_user_id as an integer.

        Returns:
            int: The HTB user ID as an integer.
        """
        return int(self.htb_user_id)
