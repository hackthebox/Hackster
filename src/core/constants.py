from pydantic import BaseModel


class Colours(BaseModel):
    """Colour codes."""

    blue: int = 0x0279FD
    bright_green: int = 0x01D277
    dark_green: int = 0x1F8B4C
    gold: int = 0xE6C200
    grass_green: int = 0x66FF00
    orange: int = 0xE67E22
    pink: int = 0xCF84E0
    purple: int = 0xB734EB
    python_blue: int = 0x4B8BBE
    python_yellow: int = 0xFFD43B
    red: int = 0xFF0000
    soft_green: int = 0x68C290
    soft_orange: int = 0xF9CB54
    soft_red: int = 0xCD6D6D
    yellow: int = 0xF8E500


class Emojis(BaseModel):
    """Emoji codes."""

    arrow_left: str = "\u2B05"  # ⬅
    arrow_right: str = "\u27A1"  # ➡
    lock: str = "\U0001F512"  # 🔒
    partying_face: str = "\U0001F973"  # 🥳
    track_next: str = "\u23ED"  # ⏭
    track_previous: str = "\u23EE"  # ⏮


class Pagination(BaseModel):
    """Pagination default settings."""

    max_size: int = 500
    timeout: int = 300  # In seconds


class Constants(BaseModel):
    """The app constants."""

    colours: Colours = Colours()
    emojis: Emojis = Emojis()
    pagination: Pagination = Pagination()

    low_latency: int = 200
    high_latency: int = 400


constants = Constants()
