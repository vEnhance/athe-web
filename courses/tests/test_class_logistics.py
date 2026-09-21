from collections.abc import Callable
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.contrib.messages import constants as message_levels
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Course, Semester
from home.models import StaffPhotoListing

URL = reverse("courses:class_logistics")


def payload(*rows: dict[str, Any]) -> dict[str, Any]:
    """Formset POST data for the given rows, each keyed by unprefixed field name."""
    data: dict[str, Any] = {
        "form-TOTAL_FORMS": len(rows),
        "form-INITIAL_FORMS": len(rows),
        "form-MIN_NUM_FORMS": 0,
        "form-MAX_NUM_FORMS": 1000,
    }
    for index, row in enumerate(rows):
        data |= {f"form-{index}-{name}": value for name, value in row.items()}
    return data


LOGISTICS = {
    "regular_meeting_time": "5pm-6pm ET on Saturday",
    "google_classroom_direct_link": "https://classroom.google.com/c/abc",
    "zoom_meeting_link": "https://zoom.us/j/123",
    "discord_webhook": "https://discord.com/api/webhooks/1/xyz",
    "discord_role_id": "987654321",
}


@pytest.fixture
def admin(
    athe: AtheClient, make_user: Callable[..., User], semester: Semester
) -> Semester:
    athe.login(make_user(username="boss", is_staff=True, is_superuser=True))
    return semester


@pytest.mark.django_db
def test_only_superusers_get_in(
    athe: AtheClient, make_user: Callable[..., User], semester: Semester
) -> None:
    assert "/login/" in athe.get(URL)["Location"]

    athe.login(make_user(username="teacher", is_staff=True))
    athe.get_redirects(reverse("courses:catalog_root"), URL)


@pytest.mark.django_db
def test_lists_this_semester_s_classes_only(
    athe: AtheClient,
    admin: Semester,
    make_semester: Callable[..., Semester],
    make_course: Callable[..., Course],
    make_user: Callable[..., User],
    make_staff_listing: Callable[..., StaffPhotoListing],
) -> None:
    listing = make_staff_listing(make_user(username="ann"), display_name="Ann Adams")
    make_course(admin, name="Geometry", instructor=listing)
    make_course(admin, name="Algebra")
    make_course(admin, name="Board Games", is_club=True)
    make_course(
        make_semester(
            name="Old Semester",
            start_date=admin.start_date.replace(year=admin.start_date.year - 1),
            end_date=admin.end_date.replace(year=admin.end_date.year - 1),
        ),
        name="Ancient History",
    )

    response = athe.get_ok(URL)
    athe.assert_testid_count(response, "logistics-row", 2)
    assert athe.texts_of(response, "logistics-name") == ["Algebra", "Geometry"]
    assert athe.texts_of(response, "logistics-instructor") == [
        "No instructor",
        "Ann Adams",
    ]
    athe.assert_testid_count(response, "logistics-photo", 1)
    assert listing.photo.url.encode() in response.content


@pytest.mark.django_db
def test_saves_every_field_of_every_class(
    athe: AtheClient, admin: Semester, make_course: Callable[..., Course]
) -> None:
    algebra = make_course(admin, name="Algebra")
    geometry = make_course(admin, name="Geometry")

    athe.post_redirects(
        URL,
        URL,
        payload(
            {"id": algebra.pk, **LOGISTICS},
            {"id": geometry.pk, **LOGISTICS, "discord_role_id": "112233"},
        ),
    )

    algebra.refresh_from_db()
    geometry.refresh_from_db()
    for field, value in LOGISTICS.items():
        assert getattr(algebra, field) == value
    assert geometry.discord_role_id == "112233"
    assert geometry.zoom_meeting_link == LOGISTICS["zoom_meeting_link"]


@pytest.mark.django_db
def test_one_bad_link_saves_nothing(
    athe: AtheClient, admin: Semester, make_course: Callable[..., Course]
) -> None:
    algebra = make_course(admin, name="Algebra")
    geometry = make_course(admin, name="Geometry")

    response = athe.post_ok(
        URL,
        payload(
            {"id": algebra.pk, **LOGISTICS},
            {"id": geometry.pk, **LOGISTICS, "zoom_meeting_link": "not a url"},
        ),
    )
    assert response.context["formset"].errors[1]["zoom_meeting_link"]

    algebra.refresh_from_db()
    assert algebra.regular_meeting_time == ""


@pytest.mark.django_db
def test_clubs_cannot_be_smuggled_in(
    athe: AtheClient, admin: Semester, make_course: Callable[..., Course]
) -> None:
    club = make_course(admin, name="Board Games", is_club=True)

    athe.post_redirects(URL, URL, payload({"id": club.pk, **LOGISTICS}))

    club.refresh_from_db()
    assert club.zoom_meeting_link == ""
    assert Course.objects.count() == 1


@pytest.mark.django_db
def test_without_a_current_semester(
    athe: AtheClient, make_user: Callable[..., User]
) -> None:
    athe.login(make_user(username="boss", is_staff=True, is_superuser=True))
    athe.get_redirects(reverse("courses:catalog_root"), URL)

    response = athe.get_ok(URL, follow=True)
    assert any(m.level == message_levels.ERROR for m in response.context["messages"])
