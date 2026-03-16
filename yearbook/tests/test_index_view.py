from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student


@pytest.mark.django_db
def test_index_view_requires_login():
    """Test that the index view requires login."""
    client = Client()
    url = reverse("yearbook:index")
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_index_view_redirects_staff_to_most_recent_semester():
    """Test that staff are redirected to the most recent semester."""
    client = Client()
    Semester.objects.create(
        name="Spring 2024",
        slug="sp24",
        start_date=(timezone.now() - timedelta(days=365)).date(),
        end_date=(timezone.now() - timedelta(days=275)).date(),
    )
    most_recent = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    User.objects.create_user(username="staff", password="password", is_staff=True)

    client.login(username="staff", password="password")
    url = reverse("yearbook:index")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse(
        "yearbook:entry_list", kwargs={"slug": most_recent.slug}
    )


@pytest.mark.django_db
def test_index_view_redirects_student_to_their_semester():
    """Test that students in the most recent semester are redirected to it."""
    client = Client()
    Semester.objects.create(
        name="Spring 2024",
        slug="sp24",
        start_date=(timezone.now() - timedelta(days=365)).date(),
        end_date=(timezone.now() - timedelta(days=275)).date(),
    )
    most_recent = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    Student.objects.create(user=user, airtable_name="Student", semester=most_recent)

    client.login(username="student", password="password")
    url = reverse("yearbook:index")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse(
        "yearbook:entry_list", kwargs={"slug": most_recent.slug}
    )


@pytest.mark.django_db
def test_index_view_redirects_to_semester_list_if_no_access():
    """Test that users without access to the most recent semester go to semester list."""
    client = Client()
    # User is in an older semester
    old_semester = Semester.objects.create(
        name="Spring 2024",
        slug="sp24",
        start_date=(timezone.now() - timedelta(days=365)).date(),
        end_date=(timezone.now() - timedelta(days=275)).date(),
    )
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    Student.objects.create(user=user, airtable_name="Student", semester=old_semester)

    client.login(username="student", password="password")
    url = reverse("yearbook:index")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse("yearbook:semester_list")


@pytest.mark.django_db
def test_index_view_redirects_to_semester_list_if_no_semesters():
    """Test that users are redirected to semester list if no semesters exist."""
    client = Client()
    User.objects.create_user(username="user", password="password")

    client.login(username="user", password="password")
    url = reverse("yearbook:index")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse("yearbook:semester_list")


@pytest.mark.django_db
def test_index_view_user_without_student_redirects_to_semester_list():
    """Test that users without a student record go to semester list."""
    client = Client()
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    User.objects.create_user(username="user", password="password")

    client.login(username="user", password="password")
    url = reverse("yearbook:index")
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse("yearbook:semester_list")
