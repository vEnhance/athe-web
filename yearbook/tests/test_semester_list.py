from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student

SEMESTER_LIST = reverse("yearbook:semester_list")


@pytest.mark.django_db
def test_semester_list_view_requires_login(athe: AtheClient):
    athe.get_redirects(reverse("login"), SEMESTER_LIST)


@pytest.mark.django_db
def test_semester_list_view_shows_all_semesters_to_staff(
    athe: AtheClient,
    semester: Semester,
    past_semester_for_yearbook: Semester,
    make_user: Callable[..., User],
):
    athe.login(make_user(username="staffuser", is_staff=True))
    response = athe.get_ok(SEMESTER_LIST)

    assert list(response.context["semesters"]) == [
        semester,
        past_semester_for_yearbook,
    ]


@pytest.mark.django_db
def test_semester_list_view_shows_a_student_only_her_own(
    athe: AtheClient,
    semester: Semester,
    past_semester_for_yearbook: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    user = make_user(username="studentuser")
    make_student(past_semester_for_yearbook, user=user)

    athe.login(user)
    response = athe.get_ok(SEMESTER_LIST)

    assert list(response.context["semesters"]) == [past_semester_for_yearbook]
    athe.assert_testid_count(response, "yearbook-semester-row", 1)


@pytest.mark.django_db
def test_semester_list_view_empty_state(
    athe: AtheClient, make_user: Callable[..., User]
):
    athe.login(make_user())
    response = athe.get_ok(SEMESTER_LIST)

    assert list(response.context["semesters"]) == []
    athe.assert_testid(response, "yearbook-semesters-empty")
