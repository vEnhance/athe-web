from collections.abc import Callable
from typing import Any

import pytest

from courses.models import Semester, Student
from housepoints.models import Award


@pytest.fixture
def award() -> Callable[..., Award]:
    """An award, defaulting to its student's house the way the views do."""

    def _make(
        semester: Semester,
        student: Student | None = None,
        *,
        award_type: str = Award.AwardType.HOMEWORK,
        points: int = 5,
        **kwargs: Any,
    ) -> Award:
        defaults = {"house": student.house if student else ""}
        return Award.objects.create(
            semester=semester,
            student=student,
            award_type=award_type,
            points=points,
            **(defaults | kwargs),
        )

    return _make
