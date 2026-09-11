from collections.abc import Callable
from datetime import timedelta

import pytest
from django.utils import timezone

from courses.models import Semester


@pytest.fixture
def past_semester(make_semester: Callable[..., Semester]) -> Semester:
    today = timezone.localdate()
    return make_semester(
        name="Past Semester",
        start_date=today - timedelta(days=120),
        end_date=today - timedelta(days=30),
    )


@pytest.fixture
def future_semester(make_semester: Callable[..., Semester]) -> Semester:
    today = timezone.localdate()
    return make_semester(
        name="Future Semester",
        start_date=today + timedelta(days=30),
        end_date=today + timedelta(days=120),
    )
