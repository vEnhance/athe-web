from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student


@pytest.mark.django_db
def test_dashboard_house_links_for_student(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    """House points links live on the dashboard now, not in the navbar."""
    make_student(semester, user=make_user(), house=Student.House.BUNNY)

    athe.login("student")
    response = athe.get_ok("/")

    assert response.context["house_display"] == "Bunnies"
    assert response.context["house_url"] == reverse(
        "housepoints:leaderboard_semester", kwargs={"slug": semester.slug}
    )
    athe.assert_testid(response, "dash-house-square", "dash-my-points-square")


@pytest.mark.django_db
def test_dashboard_bulk_award_link_for_staff(
    athe: AtheClient, make_user: Callable[..., User]
):
    """Award Points sits in the staff block, so only staff reach it."""
    make_user(username="pupil")
    make_user(username="staff", is_staff=True)

    athe.login("pupil")
    athe.assert_no_testid(athe.get_ok("/"), "dash-staff-links")

    athe.login("staff")
    athe.assert_testid(athe.get_ok("/"), "dash-staff-links")
