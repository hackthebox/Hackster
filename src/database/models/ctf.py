# flake8: noqa: D101
from sqlalchemy import Integer
from sqlalchemy.dialects.mysql import BIGINT, VARCHAR
from sqlalchemy.orm import Mapped, mapped_column, validates

from src.database.utils.password import Password, PasswordHash

from . import Base


class Ctf(Base):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(VARCHAR(255), nullable=False)
    guild_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    admin_role_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    participant_role_id: Mapped[int] = mapped_column(BIGINT(18), nullable=False)
    password: Mapped[str] = mapped_column(Password, nullable=False)

    @validates("password")
    def validate_password(self, key: str, password: str) -> PasswordHash:
        """Validate password."""
        return getattr(type(self), key).type.validator(password)
