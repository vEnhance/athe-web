from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone

from courses.models import Semester, Student
from yearbook.models import YearbookEntry


@pytest.fixture
def past_semester_for_yearbook(make_semester: Callable[..., Semester]) -> Semester:
    today = timezone.localdate()
    return make_semester(
        name="Spring 2025",
        start_date=today - timedelta(days=180),
        end_date=today - timedelta(days=90),
    )


@pytest.fixture
def make_entry() -> Callable[..., YearbookEntry]:
    def _make(student: Student, **kwargs: Any) -> YearbookEntry:
        defaults = {
            "display_name": student.airtable_name,
            "bio": f"Hello from {student.airtable_name}.",
        }
        return YearbookEntry.objects.create(student=student, **(defaults | kwargs))

    return _make
