from collections.abc import Callable
from typing import Any

import pytest
from django.conf import LazySettings
from django.contrib.auth.models import User

from home.models import StaffPhotoListing


@pytest.fixture(autouse=True)
def use_fast_password_hasher(settings: LazySettings) -> None:
    settings.PASSWORD_HASHERS = [
        "django.contrib.auth.hashers.MD5PasswordHasher",
    ]


@pytest.fixture
def staff_listing_for() -> Callable[..., StaffPhotoListing]:
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
