from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Course, Semester


@pytest.mark.django_db
def test_sign_in_sheet_is_linked_from_the_staff_block(
    athe: AtheClient, make_user: Callable[..., User]
):
    athe.login(make_user(username="staff", is_staff=True))
    response = athe.get_ok("/")

    athe.assert_testid(response, "dash-staff-links")
    assert reverse("ta_attendance:my_attendance").encode() in response.content


@pytest.mark.django_db
def test_all_attendance_link_visible_to_superuser(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_course: Callable[..., Course],
):
    make_course(semester, name="Math Club", is_club=True)

    athe.login(make_user(username="pupil_staff", is_staff=True))
    athe.assert_no_testid(
        athe.get_ok(reverse("ta_attendance:my_attendance")), "attendance-all-link"
    )

    athe.login(make_user(username="super", is_staff=True, is_superuser=True))
    athe.assert_testid(
        athe.get_ok(reverse("ta_attendance:my_attendance")), "attendance-all-link"
    )
