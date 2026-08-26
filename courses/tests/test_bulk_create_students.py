from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student

URL = reverse("courses:bulk_create_students")


@pytest.fixture
def semester():
    today = timezone.now().date()
    return Semester.objects.create(
        name="Fall 2025",
        slug="fall-2025",
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=30),
    )


@pytest.fixture
def courses(semester):
    return [
        Course.objects.create(name=name, description=name, semester=semester)
        for name in ("Algebra", "Geometry")
    ]


@pytest.fixture
def superuser_client():
    User.objects.create_user(username="root", password="password", is_superuser=True)
    client = Client()
    client.login(username="root", password="password")
    return client


@pytest.mark.django_db
def test_requires_superuser():
    assert Client().get(URL).status_code == 302

    User.objects.create_user(username="staff", password="password", is_staff=True)
    client = Client()
    client.login(username="staff", password="password")
    response = client.get(URL)
    assert response.status_code == 302
    assert response.url == reverse("home:index")


@pytest.mark.django_db
def test_creates_students_and_enrollments(superuser_client, semester, courses):
    algebra, geometry = courses
    response = superuser_client.post(
        URL,
        {
            "semester": semester.pk,
            "student_data": "Alice\tAlgebra,Geometry\nBob\tCalculus",
        },
    )
    # "Calculus" does not exist, so nothing at all is written
    assert response.status_code == 200
    assert not Student.objects.exists()

    response = superuser_client.post(
        URL,
        {
            "semester": semester.pk,
            "student_data": "Alice\tAlgebra,Geometry\nBob\tAlgebra",
        },
    )
    assert response.status_code == 302
    assert set(Student.objects.values_list("airtable_name", flat=True)) == {
        "Alice",
        "Bob",
    }
    assert set(algebra.students.values_list("airtable_name", flat=True)) == {
        "Alice",
        "Bob",
    }
    assert set(geometry.students.values_list("airtable_name", flat=True)) == {"Alice"}


@pytest.mark.django_db
def test_colon_separator_and_blank_lines(superuser_client, semester, courses):
    response = superuser_client.post(
        URL,
        {"semester": semester.pk, "student_data": "\nAlice: Algebra\n\n"},
    )
    assert response.status_code == 302
    assert list(courses[0].students.values_list("airtable_name", flat=True)) == [
        "Alice"
    ]


@pytest.mark.django_db
def test_rerunning_is_idempotent(superuser_client, semester, courses):
    data = {"semester": semester.pk, "student_data": "Alice\tAlgebra"}
    superuser_client.post(URL, data)
    superuser_client.post(URL, data)
    assert Student.objects.filter(airtable_name="Alice").count() == 1
    assert courses[0].students.count() == 1


@pytest.mark.django_db
def test_reports_malformed_lines(superuser_client, semester, courses):
    response = superuser_client.post(
        URL,
        {
            "semester": semester.pk,
            "student_data": "Alice\tAlgebra\tGeometry\n: Algebra\nCarol\tCalculus",
        },
    )
    assert response.status_code == 200
    errors = response.context["form"].errors["__all__"]
    assert "Line 1: Expected tab-separated values (got 3 parts)" in errors
    assert "Line 2: Missing airtable_name" in errors
    assert "Line 3: Invalid course names: Calculus" in errors
    assert not Student.objects.exists()


@pytest.mark.django_db
def test_rejects_ended_semester(superuser_client, semester, courses):
    today = timezone.now().date()
    semester.start_date = today - timedelta(days=60)
    semester.end_date = today - timedelta(days=1)
    semester.save()

    response = superuser_client.post(
        URL, {"semester": semester.pk, "student_data": "Alice\tAlgebra"}
    )
    assert response.status_code == 200
    assert "semester has ended" in str(response.context["form"].errors)
    assert not Student.objects.exists()
