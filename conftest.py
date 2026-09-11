from collections.abc import Callable
from datetime import timedelta
from itertools import count
from pathlib import Path
from typing import Any

import pytest
from django.conf import LazySettings
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.text import slugify

from atheweb.testsuite import PASSWORD, AtheClient
from courses.models import Course, Semester, Student
from home.models import StaffPhotoListing


@pytest.fixture(autouse=True)
def use_fast_password_hasher(settings: LazySettings) -> None:
    settings.PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]


@pytest.fixture(autouse=True)
def media_in_tmp_path(settings: LazySettings, tmp_path: Path) -> None:
    """Keep uploads written by tests out of the developer's media/ directory."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def athe() -> AtheClient:
    """The test client, plus ``login`` and the assertions in atheweb.testsuite."""
    return AtheClient()


@pytest.fixture
def make_user() -> Callable[..., User]:
    """A user whose password is ``atheweb.testsuite.PASSWORD``, so athe.login works."""

    def _make(username: str = "student", **kwargs: Any) -> User:
        return User.objects.create_user(username=username, password=PASSWORD, **kwargs)

    return _make


@pytest.fixture
def make_semester() -> Callable[..., Semester]:
    """A semester that is running right now unless given other dates."""

    def _make(name: str = "Fall 2025", **kwargs: Any) -> Semester:
        today = timezone.localdate()
        defaults = {
            "slug": slugify(name),
            "start_date": today - timedelta(days=10),
            "end_date": today + timedelta(days=80),
        }
        return Semester.objects.create(name=name, **(defaults | kwargs))

    return _make


@pytest.fixture
def semester(make_semester: Callable[..., Semester]) -> Semester:
    """The one running semester, for the many tests that only need there to be one."""
    return make_semester()


@pytest.fixture
def make_student() -> Callable[..., Student]:
    """A student in a semester, optionally tied to a user account."""
    counter = count(1)

    def _make(semester: Semester, user: User | None = None, **kwargs: Any) -> Student:
        if user is not None:
            fallback = user.get_full_name() or user.username
        else:
            fallback = f"Student {next(counter)}"
        defaults = {"airtable_name": fallback}
        return Student.objects.create(
            semester=semester, user=user, **(defaults | kwargs)
        )

    return _make


@pytest.fixture
def make_course() -> Callable[..., Course]:
    def _make(semester: Semester, name: str = "Intro to Olympiad", **kwargs: Any):
        defaults = {"description": ""}
        return Course.objects.create(
            semester=semester, name=name, **(defaults | kwargs)
        )

    return _make


@pytest.fixture
def make_staff_listing() -> Callable[..., StaffPhotoListing]:
    """Build a staff listing for a user, so they can be put in charge of a course.

    Running a course is expressed by pointing it at a ``StaffPhotoListing``
    rather than at a ``User``, so tests that need someone to be an instructor
    need one of these first.
    """

    def _make(user: User, **kwargs: Any) -> StaffPhotoListing:
        defaults = {
            "display_name": user.get_full_name() or user.username,
            "slug": f"staff-{user.pk}",
            "role": "Instructor",
            "category": StaffPhotoListing.Category.INSTRUCTOR,
            "biography": "Test bio",
            "photo": "staff_photos/test.jpg",
        }
        return StaffPhotoListing.objects.create(user=user, **(defaults | kwargs))

    return _make
