# flake8: noqa: D101
import enum

from sqlalchemy import Enum, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column

from . import Base


class RoleCategory(str, enum.Enum):
    """Categories for dynamic Discord roles."""
    RANK = "rank"
    SEASON = "season"
    SUBSCRIPTION_LABS = "subscription_labs"
    SUBSCRIPTION_ACADEMY = "subscription_academy"
    CREATOR = "creator"
    POSITION = "position"
    ACADEMY_CERT = "academy_cert"
    JOINABLE = "joinable"


class DynamicRole(Base):
    """
    A dynamically configured Discord role, managed via DB instead of env vars.

    Attributes:
        id: Primary key.
        key: Lookup key (e.g. "Omniscient", "CWPE", "vip").
        discord_role_id: The Discord snowflake ID for this role.
        category: Which group this role belongs to.
        display_name: Human-readable name shown in commands and embeds.
        description: Optional description (used for joinable roles).
        cert_full_name: Full certificate name from HTB platform (academy_cert only).
        cert_integer_id: Platform certificate ID (academy_cert only).
    """
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    discord_role_id: Mapped[int] = mapped_column(BIGINT(unsigned=True), nullable=False)
    category: Mapped[RoleCategory] = mapped_column(Enum(RoleCategory), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(String(256), nullable=True, default=None)
    cert_full_name: Mapped[str] = mapped_column(String(128), nullable=True, default=None)
    cert_integer_id: Mapped[int] = mapped_column(Integer, nullable=True, default=None)

    __table_args__ = (
        UniqueConstraint("key", "category", name="uq_dynamic_role_key_category"),
    )
