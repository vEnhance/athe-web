"""The fixed grid of weekend time slots students mark themselves available for.

Everything is Eastern time, which is also ``settings.TIME_ZONE``, so slots need
no conversion anywhere: they are labels on a form, not points in time.
"""

from datetime import time

#: Short name of the timezone every slot is quoted in.
ZONE = "ET"

#: Days of the week classes are held on, in the order the grid shows them.
DAYS: tuple[tuple[str, str], ...] = (("sat", "Saturday"), ("sun", "Sunday"))

#: The grid runs from 8am to midnight in half-hour slots.
FIRST_HOUR = 8
LAST_HOUR = 24
SLOT_MINUTES = 30


def slot_starts() -> list[time]:
    """Start time of each slot in a day, from FIRST_HOUR up to LAST_HOUR."""
    return [
        time(minute // 60, minute % 60)
        for minute in range(FIRST_HOUR * 60, LAST_HOUR * 60, SLOT_MINUTES)
    ]


def slot_key(day: str, start: time) -> str:
    """The stored form of one slot, e.g. ``sat-0830``."""
    return f"{day}-{start.hour:02d}{start.minute:02d}"


def time_label(start: time) -> str:
    """A 12-hour clock label, e.g. ``8:30 AM``.

    Written out rather than left to ``strftime``, whose 12-hour formats either
    zero-pad or need a platform-specific ``%-I``.
    """
    return f"{start.hour % 12 or 12}:{start.minute:02d} {'AM' if start.hour < 12 else 'PM'}"


def slot_label(day: str, start: time) -> str:
    """A human-readable label for one slot, e.g. ``Saturday 8:30 AM ET``."""
    day_label = dict(DAYS)[day]
    return f"{day_label} {time_label(start)} {ZONE}"


def slot_choices() -> list[tuple[str, str]]:
    """Every slot as a Django choices pair, ordered day-major then by time."""
    return [
        (slot_key(day, start), slot_label(day, start))
        for day, _ in DAYS
        for start in slot_starts()
    ]


#: Set of every valid slot key, for validating stored and submitted values.
SLOT_KEYS = frozenset(key for key, _ in slot_choices())
