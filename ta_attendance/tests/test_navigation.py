from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester

from ta_attendance.models import Attendance


@pytest.mark.django_db
def test_navigation_link_visible_to_staff():
    """Test that the TA Attendance link is visible in the navigation for staff."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    client.login(username="staff", password="password")
    response = client.get(reverse("home:index"))

    content = response.content.decode()
    assert "TA Sign-in Sheet" in content
    assert reverse("ta_attendance:my_attendance") in content


@pytest.mark.django_db
def test_all_attendance_link_visible_to_superuser():
    """Test that the All Attendance link is visible for superusers."""
    client = Client()
    user = User.objects.create_user(
        username="super", password="password", is_superuser=True, is_staff=True
    )

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Course.objects.create(
        name="Math Club",
        description="Math",
        semester=semester,
        is_club=True,
    )

    Attendance.objects.create(user=user, date=date.today(), club=Course.objects.first())

    client.login(username="super", password="password")
    response = client.get(reverse("ta_attendance:my_attendance"))

    content = response.content.decode()
    assert "View All Attendance Records" in content
    assert reverse("ta_attendance:all_attendance") in content
