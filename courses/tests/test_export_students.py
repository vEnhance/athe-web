import csv
from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.http import HttpResponse
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Course, Semester, Student
from courses.views import STUDENT_COLUMNS
from reg.models import StudentRegistration

EXPORT = reverse("courses:export_students")


@pytest.fixture
def staff(athe: AtheClient, make_user: Callable[..., User]) -> User:
    return athe.login(make_user(username="staff", is_staff=True))


def rows(response: HttpResponse) -> list[dict[str, str]]:
    return list(csv.DictReader(response.content.decode().splitlines()))


@pytest.mark.django_db
def test_non_staff_redirected(
    athe: AtheClient, semester: Semester, make_user: Callable[..., User]
):
    athe.login(make_user())
    athe.get_redirects(reverse("courses:catalog_root"), EXPORT)


@pytest.mark.django_db
def test_unauthenticated_redirected(athe: AtheClient, semester: Semester):
    assert athe.get(EXPORT).status_code == 302


@pytest.mark.django_db
def test_no_current_semester_redirects(
    athe: AtheClient, past_semester: Semester, staff: User
):
    athe.get_redirects(reverse("courses:catalog_root"), EXPORT)


@pytest.mark.django_db
def test_registered_student_row(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    user = make_user(username="lucy", email="account@example.com")
    student = make_student(
        semester, user=user, airtable_name="Lucy L", house=Student.House.OWL
    )
    StudentRegistration.objects.create(
        student=student,
        email="lucy@example.com",
        parent_email="parent@example.com",
        discord_username="lucylu",
    )
    make_course(semester, name="Geometry").students.add(student)
    make_course(semester, name="Algebra").students.add(student)
    make_course(semester, name="Combo")
    make_course(semester, name="Chess", kind=Course.Kind.CLUB).students.add(student)

    (row,) = rows(athe.get_ok(EXPORT))

    assert row == {
        "airtable_name": "Lucy L",
        "username": "lucy",
        "email": "lucy@example.com",
        "parent_email": "parent@example.com",
        "discord_username": "lucylu",
        "classes": "Algebra; Geometry",
        "house": "Owls",
        "Algebra": "1",
        "Combo": "0",
        "Geometry": "1",
    }


@pytest.mark.django_db
def test_account_email_used_when_registration_has_none(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    user = make_user(username="lucy", email="account@example.com")
    student = make_student(semester, user=user)
    StudentRegistration.objects.create(
        student=student, email="", parent_email="", discord_username=""
    )

    (row,) = rows(athe.get_ok(EXPORT))

    assert row["email"] == "account@example.com"


@pytest.mark.django_db
def test_unclaimed_student_row_is_blank(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
):
    make_student(semester, airtable_name="Nobody Yet")

    (row,) = rows(athe.get_ok(EXPORT))

    assert row == {
        "airtable_name": "Nobody Yet",
        "username": "",
        "email": "",
        "parent_email": "",
        "discord_username": "",
        "classes": "",
        "house": "",
    }


@pytest.mark.django_db
def test_class_columns_cover_the_semester_in_name_order(
    athe: AtheClient,
    semester: Semester,
    past_semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    make_student(semester)
    for name in ("Nifty NT", "AIME Combo", "Comical Combo"):
        make_course(semester, name=name)
    make_course(semester, name="Chess", kind=Course.Kind.CLUB)
    make_course(past_semester, name="Old Geometry")

    (row,) = rows(athe.get_ok(EXPORT))

    assert list(row)[len(STUDENT_COLUMNS) :] == [
        "AIME Combo",
        "Comical Combo",
        "Nifty NT",
    ]


@pytest.mark.django_db
def test_classes_sharing_a_name_get_their_own_column(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    """A repeated header would collide into one column, losing a class."""
    student = make_student(semester)
    first = make_course(semester, name="Geometry")
    second = make_course(semester, name="Geometry")
    second.students.add(student)

    (row,) = rows(athe.get_ok(EXPORT))

    assert row["Geometry"] == "0"
    assert row[f"Geometry (#{second.pk})"] == "1"
    assert row["classes"] == f"Geometry (#{second.pk})"
    assert first.pk < second.pk


@pytest.mark.django_db
def test_only_current_semester_students(
    athe: AtheClient,
    semester: Semester,
    past_semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
):
    make_student(semester, airtable_name="Current Kid")
    make_student(past_semester, airtable_name="Old Kid")

    response = athe.get_ok(EXPORT)

    assert [row["airtable_name"] for row in rows(response)] == ["Current Kid"]
    assert response["Content-Disposition"] == (
        f'attachment; filename="{semester.slug}-students.csv"'
    )


@pytest.mark.django_db
def test_query_count(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    course = make_course(semester, name="Geometry")
    for i in range(5):
        student = make_student(semester, airtable_name=f"Student {i}")
        StudentRegistration.objects.create(
            student=student,
            email=f"s{i}@example.com",
            parent_email=f"p{i}@example.com",
            discord_username=f"s{i}",
        )
        course.students.add(student)

    with CaptureQueriesContext(connection) as queries:
        response = athe.get_ok(EXPORT)

    assert len(rows(response)) == 5
    assert len(queries.captured_queries) <= 6, len(queries.captured_queries)
