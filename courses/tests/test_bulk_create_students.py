from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student

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
def test_creates_students(superuser_client, semester):
    response = superuser_client.post(
        URL,
        {"semester": semester.pk, "student_data": "Alice Anderson\nBob Brown"},
    )
    assert response.status_code == 302
    assert set(Student.objects.values_list("airtable_name", flat=True)) == {
        "Alice Anderson",
        "Bob Brown",
    }
    # Classes and houses are left for the uploaded matching.
    assert not Student.objects.exclude(house="").exists()
    assert not Student.objects.filter(enrolled_courses__isnull=False).exists()


@pytest.mark.django_db
def test_blank_lines_and_surrounding_space(superuser_client, semester):
    response = superuser_client.post(
        URL,
        {"semester": semester.pk, "student_data": "\n  Alice Anderson  \n\n"},
    )
    assert response.status_code == 302
    assert list(Student.objects.values_list("airtable_name", flat=True)) == [
        "Alice Anderson"
    ]


@pytest.mark.django_db
def test_rerunning_is_idempotent(superuser_client, semester):
    data = {"semester": semester.pk, "student_data": "Alice Anderson"}
    superuser_client.post(URL, data)
    superuser_client.post(URL, data)
    assert Student.objects.filter(airtable_name="Alice Anderson").count() == 1


@pytest.mark.django_db
def test_rejects_duplicate_and_overlong_names(superuser_client, semester):
    response = superuser_client.post(
        URL,
        {
            "semester": semester.pk,
            "student_data": "Alice\nAlice\n" + "x" * (Student.NAME_MAX_LENGTH + 1),
        },
    )
    assert response.status_code == 200
    errors = response.context["form"].errors["__all__"]
    assert "Line 2: 'Alice' is listed twice." in errors
    assert "too long" in errors[1]
    assert not Student.objects.exists()


@pytest.mark.django_db
def test_rejects_empty_list(superuser_client, semester):
    response = superuser_client.post(
        URL, {"semester": semester.pk, "student_data": " \n "}
    )
    assert response.status_code == 200
    assert response.context["form"].errors["student_data"]


@pytest.mark.django_db
def test_rejects_ended_semester(superuser_client, semester):
    today = timezone.now().date()
    semester.start_date = today - timedelta(days=60)
    semester.end_date = today - timedelta(days=1)
    semester.save()

    response = superuser_client.post(
        URL, {"semester": semester.pk, "student_data": "Alice"}
    )
    assert response.status_code == 200
    assert "semester has ended" in str(response.context["form"].errors)
    assert not Student.objects.exists()
