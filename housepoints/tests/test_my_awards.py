from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student
from housepoints.models import Award

MY_AWARDS = reverse("housepoints:my_awards")


def award_types(response) -> list[str]:
    return [award.award_type for award in response.context["awards"]]


@pytest.mark.django_db
def test_my_awards_requires_login(athe: AtheClient):
    athe.get_redirects(reverse("login"), MY_AWARDS)


@pytest.mark.django_db
def test_my_awards_shows_user_awards(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    award: Callable[..., Award],
):
    student = make_student(
        semester, user=make_user(username="student"), house=Student.House.BUNNY
    )
    earned = award(
        semester,
        student,
        award_type=Award.AwardType.INTRO_POST,
        points=1,
        description="Posted intro",
    )

    athe.login("student")
    response = athe.get_ok(MY_AWARDS)

    assert list(response.context["awards"]) == [earned]
    athe.assert_testid_count(response, "my-awards-row", 1)


@pytest.mark.django_db
def test_my_awards_shows_semester_totals(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    award: Callable[..., Award],
):
    student = make_student(
        semester, user=make_user(username="student"), house=Student.House.CAT
    )
    award(semester, student, award_type=Award.AwardType.HOMEWORK)
    award(semester, student, award_type=Award.AwardType.CLASS_ATTENDANCE)

    athe.login("student")
    response = athe.get_ok(MY_AWARDS)

    assert response.context["semester_totals"] == [
        {"semester": semester, "house": "Cats", "total": 10}
    ]


@pytest.mark.django_db
def test_my_awards_only_shows_own_awards(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    award: Callable[..., Award],
):
    alice = make_student(
        semester, user=make_user(username="alice"), house=Student.House.OWL
    )
    bob = make_student(
        semester, user=make_user(username="bob"), house=Student.House.CAT
    )
    award(semester, alice, award_type=Award.AwardType.POTD, points=20)
    award(semester, bob, award_type=Award.AwardType.HOMEWORK)

    athe.login("alice")
    response = athe.get_ok(MY_AWARDS)

    assert award_types(response) == [Award.AwardType.POTD]


@pytest.mark.django_db
def test_my_awards_is_empty_for_someone_who_has_earned_nothing(
    athe: AtheClient, make_user: Callable[..., User]
):
    make_user(username="newcomer")

    athe.login("newcomer")
    response = athe.get_ok(MY_AWARDS)

    assert list(response.context["awards"]) == []
    athe.assert_testid(response, "my-awards-empty")
