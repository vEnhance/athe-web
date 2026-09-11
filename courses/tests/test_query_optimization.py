from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Course, Semester, Student

MY_COURSES = reverse("courses:my_courses")
MY_CLUBS = reverse("courses:my_clubs")


def names(response, key: str) -> set[str]:
    return {course.name for course in response.context[key]}


@pytest.mark.django_db
def test_my_courses_query_count(
    athe: AtheClient,
    semester: Semester,
    past_semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
    make_staff_listing,
):
    """Enrolments across semesters must not turn into a query each."""
    user = make_user()
    for sem in (semester, past_semester):
        student = make_student(sem, user=user)
        for name in ("Math 101", "CS 101"):
            make_course(sem, name=f"{name} {sem.slug}").students.add(student)
    make_course(semester, name="Taught", instructor=make_staff_listing(user))

    athe.login(user)
    with CaptureQueriesContext(connection) as queries:
        response = athe.get_ok(MY_COURSES)

    assert len(queries.captured_queries) <= 6, len(queries.captured_queries)
    assert len(response.context["enrolled_courses"]) == 5


@pytest.mark.django_db
def test_my_courses_shows_enrolled_and_taught_but_not_clubs(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
    make_staff_listing,
):
    user = make_user()
    student = make_student(semester, user=user)
    make_course(semester, name="Math 101").students.add(student)
    make_course(semester, name="CS 101", instructor=make_staff_listing(user))
    make_course(semester, name="Chess Club", is_club=True).students.add(student)

    athe.login(user)
    response = athe.get_ok(MY_COURSES)

    assert names(response, "enrolled_courses") == {"Math 101", "CS 101"}


@pytest.mark.django_db
def test_my_clubs_query_count(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
    make_staff_listing,
):
    """Clubs in the semester must not turn into a query each."""
    user = make_user()
    student = make_student(semester, user=user)
    for name in ("Chess Club", "Math Club"):
        make_course(semester, name=name, is_club=True).students.add(student)
    make_course(
        semester, name="Art Club", is_club=True, instructor=make_staff_listing(user)
    )
    make_course(semester, name="Music Club", is_club=True)

    athe.login(user)
    with CaptureQueriesContext(connection) as queries:
        response = athe.get_ok(MY_CLUBS)

    assert len(queries.captured_queries) <= 7, len(queries.captured_queries)
    assert len(response.context["enrolled_clubs"]) == 3
    assert len(response.context["available_clubs"]) == 1


@pytest.mark.django_db
def test_my_clubs_counts_a_club_you_run_as_enrolled(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
    make_staff_listing,
):
    user = make_user()
    student = make_student(semester, user=user)
    make_course(semester, name="Chess Club", is_club=True).students.add(student)
    make_course(
        semester, name="Math Club", is_club=True, instructor=make_staff_listing(user)
    )
    make_course(semester, name="Art Club", is_club=True)

    athe.login(user)
    response = athe.get_ok(MY_CLUBS)

    assert names(response, "enrolled_clubs") == {"Chess Club", "Math Club"}
    assert names(response, "available_clubs") == {"Art Club"}


@pytest.mark.django_db
def test_my_clubs_no_current_semester(
    athe: AtheClient,
    past_semester: Semester,
    make_user: Callable[..., User],
    make_course: Callable[..., Course],
):
    """With nothing unfinished on the books, my_clubs has nothing to offer."""
    make_course(past_semester, name="Old Club", is_club=True)

    athe.login(make_user())
    response = athe.get_ok(MY_CLUBS)

    assert response.context["has_current_semester"] is False
    assert names(response, "enrolled_clubs") == set()
    assert names(response, "available_clubs") == set()
