import json

from app.logging_config import scrub_event
from app.pii import scrub_text


def test_scrub_email() -> None:
    out = scrub_text("Email me at student@vinuni.edu.vn")
    assert "student@" not in out
    assert "REDACTED_EMAIL" in out


def test_scrub_common_vietnamese_phone_formats() -> None:
    phone_numbers = (
        "0901234567",
        "090 123 4567",
        "090.123.4567",
        "090-123-4567",
        "+84 90 123 4567",
    )

    for phone_number in phone_numbers:
        out = scrub_text(f"Contact: {phone_number}")
        assert phone_number not in out
        assert "REDACTED_PHONE_VN" in out


def test_scrub_cccd_and_credit_card() -> None:
    raw_values = {
        "001203004567": "REDACTED_CCCD",
        "4111 1111 1111 1111": "REDACTED_CREDIT_CARD",
    }

    for raw, marker in raw_values.items():
        out = scrub_text(f"Sensitive: {raw}")
        assert raw not in out
        assert marker in out


def test_log_processor_scrubs_nested_values() -> None:
    event = {
        "session_id": "student@vinuni.edu.vn",
        "payload": {
            "contacts": ["090 123 4567", {"cccd": "001203004567"}],
            "card": "4111 1111 1111 1111",
        },
    }

    rendered = json.dumps(scrub_event(None, "info", event))

    assert "student@" not in rendered
    assert "090 123 4567" not in rendered
    assert "001203004567" not in rendered
    assert "4111 1111 1111 1111" not in rendered
