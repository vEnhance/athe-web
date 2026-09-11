from collections.abc import Callable
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student
from housepoints.models import Award


def semester_url(semester: Semester) -> str:
    return reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug})


def totals(response) -> dict[str, int]:
    return {
        entry["house_display"]: entry["total_points"]
        for entry in response.context["leaderboard_data"]
    }


@pytest.mark.django_db
def test_leaderboard_loads_for_anonymous_visitors(athe: AtheClient):
    athe.get_ok(reverse("housepoints:leaderboard"))


@pytest.mark.django_db
def test_leaderboard_calculates_totals(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    award: Callable[..., Award],
):
    owl = make_student(semester, house=Student.House.OWL)
    cat = make_student(semester, house=Student.House.CAT)
    award(semester, owl, award_type=Award.AwardType.CLASS_ATTENDANCE)
    award(semester, owl, award_type=Award.AwardType.HOMEWORK)
    award(semester, cat, award_type=Award.AwardType.CLASS_ATTENDANCE)

    athe.login(make_user(username="staff", is_staff=True))
    response = athe.get_ok(semester_url(semester))

    assert totals(response)["Owls"] == 10
    assert totals(response)["Cats"] == 5


@pytest.mark.django_db
def test_leaderboard_respects_freeze_date(
    athe: AtheClient,
    make_semester: Callable[..., Semester],
    make_student: Callable[..., Student],
    award: Callable[..., Award],
):
    """Points awarded after the freeze are off the public leaderboard."""
    freeze = timezone.now() - timedelta(days=1)
    semester = make_semester(house_points_freeze_date=freeze)
    student = make_student(semester, house=Student.House.BLOB)
    award(semester, student, points=5, awarded_at=freeze - timedelta(hours=1))
    award(semester, student, points=10, awarded_at=freeze + timedelta(hours=1))

    response = athe.get_ok(semester_url(semester))

    assert totals(response)["Blobs"] == 5
    assert response.context["is_frozen"] is True
    assert response.context["freeze_date"] == freeze
    athe.assert_testid(response, "leaderboard-freeze-notice")


@pytest.mark.django_db
def test_leaderboard_shows_all_houses(athe: AtheClient, semester: Semester):
    """Every house has a row, whether or not it has scored."""
    response = athe.get_ok(semester_url(semester))

    assert totals(response) == {house.label: 0 for house in Student.House}


@pytest.mark.django_db
def test_leaderboard_uses_current_semester_when_no_slug(
    athe: AtheClient,
    semester: Semester,
    make_semester: Callable[..., Semester],
):
    today = timezone.localdate()
    make_semester(
        name="Spring 2025",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=100),
    )

    response = athe.get_ok(reverse("housepoints:leaderboard"))

    assert response.context["semester"] == semester


@pytest.mark.django_db
def test_leaderboard_falls_back_to_latest_when_no_current(
    athe: AtheClient, make_semester: Callable[..., Semester]
):
    today = timezone.localdate()
    make_semester(
        name="Spring 2024",
        start_date=today - timedelta(days=300),
        end_date=today - timedelta(days=200),
    )
    latest = make_semester(
        name="Fall 2024",
        start_date=today - timedelta(days=150),
        end_date=today - timedelta(days=50),
    )

    response = athe.get_ok(reverse("housepoints:leaderboard"))

    assert response.context["semester"] == latest


@pytest.mark.django_db
def test_leaderboard_says_so_when_there_are_no_semesters(athe: AtheClient):
    response = athe.get_ok(reverse("housepoints:leaderboard"))

    assert response.context["semester"] is None
    athe.assert_testid(response, "leaderboard-no-semesters")


@pytest.mark.django_db
def test_leaderboard_links_a_student_to_her_own_house_only(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    make_student(semester, user=make_user(username="owlet"), house=Student.House.OWL)

    athe.login("owlet")
    response = athe.get_ok(semester_url(semester))

    athe.assert_testid_count(response, "leaderboard-own-house", 1)
    athe.assert_no_testid(response, "leaderboard-house-link")


@pytest.mark.django_db
def test_leaderboard_links_staff_into_every_house(
    athe: AtheClient, semester: Semester, make_user: Callable[..., User]
):
    athe.login(make_user(username="staff", is_staff=True))
    response = athe.get_ok(semester_url(semester))

    athe.assert_testid_count(
        response, "leaderboard-house-link", len(Student.House.choices)
    )
