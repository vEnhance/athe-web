import datetime

import pytest

from home.templatetags.local_time import local_datetime


@pytest.fixture
def aware_dt() -> datetime.datetime:
    """A timezone-aware datetime: 2026-03-05 20:00 UTC = 15:00 America/New_York."""
    return datetime.datetime(2026, 3, 5, 20, 0, 0, tzinfo=datetime.timezone.utc)


def test_returns_time_element(aware_dt: datetime.datetime) -> None:
    result = str(local_datetime(aware_dt, "F j, Y, g:i A e"))
    assert result.startswith("<time ")
    assert result.endswith("</time>")


def test_datetime_attribute_is_iso(aware_dt: datetime.datetime) -> None:
    result = str(local_datetime(aware_dt, "F j, Y, g:i A e"))
    assert 'datetime="2026-03-05T20:00:00+00:00"' in result


def test_display_uses_server_timezone(aware_dt: datetime.datetime) -> None:
    # 20:00 UTC = 15:00 America/New_York (EST, UTC-5)
    result = str(local_datetime(aware_dt, "g:i A e"))
    assert "3:00 PM" in result
    assert "EST" in result


def test_empty_value_returns_empty_string() -> None:
    assert local_datetime(None, "F j, Y") == ""


def test_plain_date_returns_formatted_string() -> None:
    d = datetime.date(2026, 3, 5)
    result = local_datetime(d, "F j, Y")
    assert result == "March 5, 2026"
    assert "<time" not in str(result)


def test_has_interactive_class(aware_dt: datetime.datetime) -> None:
    result = str(local_datetime(aware_dt, "F j, Y"))
    assert 'class="local-datetime"' in result
