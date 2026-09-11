from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Course, Semester

PAST_CLUBS = reverse("courses:past_clubs")


def listed(response) -> list[str]:
    return [club.name for club in response.context["past_clubs"]]


@pytest.fixture
def student(athe: AtheClient, make_user: Callable[..., User]) -> User:
    return athe.login(make_user())


@pytest.mark.django_db
def test_past_clubs_requires_login(athe: AtheClient):
    athe.get_redirects(reverse("login"), PAST_CLUBS)


@pytest.mark.django_db
def test_past_clubs_shows_clubs_the_reader_was_never_in(
    athe: AtheClient,
    student: User,
    past_semester: Semester,
    make_course: Callable[..., Course],
):
    """Past clubs are a read-only archive, so enrolment does not gate them."""
    make_course(past_semester, name="Chess Club", is_club=True)
    make_course(past_semester, name="Art Club", is_club=True)

    response = athe.get_ok(PAST_CLUBS)

    assert sorted(listed(response)) == ["Art Club", "Chess Club"]
    athe.assert_testid_count(response, "course-list-item", 2)


@pytest.mark.django_db
def test_past_clubs_excludes_invisible_semesters(
    athe: AtheClient,
    student: User,
    past_semester: Semester,
    make_semester: Callable[..., Semester],
    make_course: Callable[..., Course],
):
    hidden = make_semester(
        name="Invisible Semester",
        start_date=past_semester.start_date.replace(year=2020),
        end_date=past_semester.end_date.replace(year=2020),
        visible=False,
    )
    make_course(past_semester, name="Visible Club", is_club=True)
    make_course(hidden, name="Invisible Club", is_club=True)

    assert listed(athe.get_ok(PAST_CLUBS)) == ["Visible Club"]


@pytest.mark.django_db
def test_past_clubs_excludes_active_and_future_semesters(
    athe: AtheClient,
    student: User,
    semester: Semester,
    past_semester: Semester,
    future_semester: Semester,
    make_course: Callable[..., Course],
):
    make_course(past_semester, name="Past Club", is_club=True)
    make_course(semester, name="Active Club", is_club=True)
    make_course(future_semester, name="Future Club", is_club=True)

    assert listed(athe.get_ok(PAST_CLUBS)) == ["Past Club"]


@pytest.mark.django_db
def test_past_clubs_excludes_regular_courses(
    athe: AtheClient,
    student: User,
    past_semester: Semester,
    make_course: Callable[..., Course],
):
    make_course(past_semester, name="Chess Club", is_club=True)
    make_course(past_semester, name="Math 101")

    assert listed(athe.get_ok(PAST_CLUBS)) == ["Chess Club"]


@pytest.mark.django_db
def test_past_clubs_are_linked_whoever_is_reading(
    athe: AtheClient,
    past_semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., None],
    make_course: Callable[..., Course],
):
    """Every past club is a link, whether or not this reader was in its semester;
    the course page does its own access check when they follow it."""
    club = make_course(past_semester, name="Chess Club", is_club=True)
    outsider = make_user(username="outsider")
    alumna = make_user(username="alumna")
    make_student(past_semester, user=alumna)
    staff = make_user(username="staff", is_staff=True)
    club_url = reverse("courses:course_detail", kwargs={"pk": club.pk})

    for user in (outsider, alumna, staff):
        athe.login(user)
        response = athe.get_ok(PAST_CLUBS)
        assert listed(response) == ["Chess Club"]
        assert f'href="{club_url}"'.encode() in response.content


@pytest.mark.django_db
def test_past_clubs_empty_state(athe: AtheClient, student: User, semester: Semester):
    response = athe.get_ok(PAST_CLUBS)

    assert listed(response) == []
    athe.assert_testid(response, "past-clubs-empty")
