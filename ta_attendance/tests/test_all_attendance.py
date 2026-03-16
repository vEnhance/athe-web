from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester

from ta_attendance.models import Attendance


@pytest.mark.django_db
def test_all_attendance_requires_login():
    """Test that all_attendance view requires authentication."""
    client = Client()
    url = reverse("ta_attendance:all_attendance")
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_all_attendance_requires_superuser():
    """Test that all_attendance view requires superuser status."""
    client = Client()

    # Test with regular user
    User.objects.create_user(username="regular", password="password")
    client.login(username="regular", password="password")
    url = reverse("ta_attendance:all_attendance")
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse("home:index")

    # Test with staff (but not superuser)
    User.objects.create_user(username="staff", password="password", is_staff=True)
    client.login(username="staff", password="password")
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse("home:index")


@pytest.mark.django_db
def test_all_attendance_superuser_access():
    """Test that superusers can access all_attendance view."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    client.login(username="super", password="password")
    url = reverse("ta_attendance:all_attendance")
    response = client.get(url)

    assert response.status_code == 200
    assert "records" in response.context


@pytest.mark.django_db
def test_all_attendance_shows_all_records():
    """Test that all_attendance shows records from all users."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)
    user1 = User.objects.create_user(
        username="staff1", password="password", is_staff=True
    )
    user2 = User.objects.create_user(
        username="staff2", password="password", is_staff=True
    )

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    club = Course.objects.create(
        name="Math Club",
        description="Math",
        semester=semester,
        is_club=True,
    )

    # Create attendance for both users
    Attendance.objects.create(user=user1, date=date.today(), club=club)
    Attendance.objects.create(
        user=user2, date=date.today() - timedelta(days=1), club=club
    )

    client.login(username="super", password="password")
    url = reverse("ta_attendance:all_attendance")
    response = client.get(url)

    records = response.context["records"]
    assert len(records) == 2


@pytest.mark.django_db
def test_all_attendance_displays_user_name():
    """Test that all_attendance displays the user's name correctly."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)
    user = User.objects.create_user(
        username="staff",
        password="password",
        is_staff=True,
        first_name="John",
        last_name="Doe",
    )

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    club = Course.objects.create(
        name="Math Club",
        description="Math",
        semester=semester,
        is_club=True,
    )

    Attendance.objects.create(user=user, date=date.today(), club=club)

    client.login(username="super", password="password")
    url = reverse("ta_attendance:all_attendance")
    response = client.get(url)

    content = response.content.decode()
    assert "John Doe" in content
