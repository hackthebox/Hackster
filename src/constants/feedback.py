"""Feedback form choices aligned with the feedback service ingest schema."""

from __future__ import annotations

from discord import OptionChoice

# (display label, ingest slug) — matches feedback service FeedbackKind
FEEDBACK_KINDS: list[tuple[str, str]] = [
    ("Bug report", "bug"),
    ("Feature request", "product_feature"),
    ("Suggestion", "suggestion"),
    ("Comment", "comment"),
    ("Review", "review"),
    ("Other", "other"),
]

# (display label, ingest slug) — matches feedback service HTBPlatform catalog
FEEDBACK_PLATFORMS: list[tuple[str, str]] = [
    ("HTB Labs", "htb_labs"),
    ("HTB Academy", "htb_academy"),
    ("HTB Enterprise", "htb_enterprise"),
    ("HTB CTF", "htb_ctf"),
    ("HTB Discord", "htb_discord"),
    ("HTB Account", "htb_account"),
    ("HTB Profile", "htb_profile"),
    ("HTB Website", "htb_landing_website"),
    ("Other", "other"),
]

FEEDBACK_KIND_VALUES = [value for _, value in FEEDBACK_KINDS]
FEEDBACK_PLATFORM_VALUES = [value for _, value in FEEDBACK_PLATFORMS]


def feedback_kind_choices() -> list[OptionChoice]:
    return [OptionChoice(label, value) for label, value in FEEDBACK_KINDS]


def feedback_platform_choices() -> list[OptionChoice]:
    return [OptionChoice(label, value) for label, value in FEEDBACK_PLATFORMS]
