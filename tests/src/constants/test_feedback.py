from src.constants.feedback import (
    FEEDBACK_KIND_VALUES,
    FEEDBACK_PLATFORM_VALUES,
    feedback_kind_choices,
    feedback_platform_choices,
)


def test_feedback_kind_values_match_feedback_service():
    assert "bug" in FEEDBACK_KIND_VALUES
    assert "product_feature" in FEEDBACK_KIND_VALUES
    assert "other" in FEEDBACK_KIND_VALUES


def test_feedback_platform_values_match_feedback_service_catalog():
    assert "htb_labs" in FEEDBACK_PLATFORM_VALUES
    assert "htb_academy" in FEEDBACK_PLATFORM_VALUES
    assert "htb_discord" in FEEDBACK_PLATFORM_VALUES


def test_option_choices_use_ingest_slugs():
    kind_values = {choice.value for choice in feedback_kind_choices()}
    platform_values = {choice.value for choice in feedback_platform_choices()}
    assert kind_values == set(FEEDBACK_KIND_VALUES)
    assert platform_values == set(FEEDBACK_PLATFORM_VALUES)
