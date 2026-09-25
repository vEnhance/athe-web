from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from courses.models import Course, CourseMeeting, Semester, Student
from tickets.models import Ticket


@pytest.fixture
def lucy(make_user: Callable[..., User]) -> User:
    return make_user(username="lucy", first_name="Lucy")


@pytest.fixture
def student(
    semester: Semester, lucy: User, make_student: Callable[..., Student]
) -> Student:
    return make_student(semester, user=lucy)


@pytest.fixture
def staffer(make_user: Callable[..., User]) -> User:
    return make_user(username="alex", first_name="Alex", is_staff=True)


@pytest.fixture
def office_hours(make_course: Callable[..., Course], semester: Semester) -> Course:
    return make_course(
        semester,
        name="OH (Alex + Heather)",
        kind=Course.Kind.OFFICE_HOURS,
    )


@pytest.fixture
def make_meeting() -> Callable[..., CourseMeeting]:
    def _make(course: Course, days: float = 2, **kwargs: Any) -> CourseMeeting:
        return CourseMeeting.objects.create(
            course=course, start_time=timezone.now() + timedelta(days=days), **kwargs
        )

    return _make


@pytest.fixture
def sitting(
    office_hours: Course, make_meeting: Callable[..., CourseMeeting]
) -> CourseMeeting:
    return make_meeting(office_hours)


@pytest.fixture
def make_ticket() -> Callable[..., Ticket]:
    def _make(student: Student, title: str = "FLT", **kwargs: Any) -> Ticket:
        defaults = {
            "question": "How do I solve this Diophantine? $a^n+b^n=c^n$, $n>2$."
        }
        return Ticket.objects.create(
            student=student, title=title, **(defaults | kwargs)
        )

    return _make
