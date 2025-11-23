from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.utils import timezone

from courses.models import Course, Semester

from ta_attendance.models import Attendance


@pytest.mark.django_db
def test_attendance_creation():
    """Test basic attendance record creation."""
    user = User.objects.create_user(
        username="staff", password="password", is_staff=True
    )
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    club = Course.objects.create(
        name="Math Club",
        description="Math enthusiasts",
        semester=semester,
        is_club=True,
    )

    attendance = Attendance.objects.create(
        user=user,
        date=date.today(),
        club=club,
    )

    assert attendance.user == user
    assert attendance.date == date.today()
    assert attendance.club == club
    assert str(attendance) == f"{user.username} - Math Club on {date.today()}"


@pytest.mark.django_db
def test_attendance_unique_constraint():
    """Test that user, date, club combination must be unique."""
    user = User.objects.create_user(
        username="staff", password="password", is_staff=True
    )
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    club = Course.objects.create(
        name="Math Club",
        description="Math enthusiasts",
        semester=semester,
        is_club=True,
    )

    # Create first attendance record
    Attendance.objects.create(user=user, date=date.today(), club=club)

    # Try to create duplicate - should fail
    with pytest.raises(IntegrityError):
        Attendance.objects.create(user=user, date=date.today(), club=club)


@pytest.mark.django_db
def test_attendance_same_user_different_dates():
    """Test that same user can have attendance on different dates."""
    user = User.objects.create_user(
        username="staff", password="password", is_staff=True
    )
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    club = Course.objects.create(
        name="Math Club",
        description="Math enthusiasts",
        semester=semester,
        is_club=True,
    )

    # Create attendance on different dates
    Attendance.objects.create(user=user, date=date.today(), club=club)
    Attendance.objects.create(
        user=user, date=date.today() - timedelta(days=1), club=club
    )

    assert Attendance.objects.filter(user=user).count() == 2


@pytest.mark.django_db
def test_attendance_same_date_different_clubs():
    """Test that same user can attend different clubs on the same date."""
    user = User.objects.create_user(
        username="staff", password="password", is_staff=True
    )
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    club1 = Course.objects.create(
        name="Math Club",
        description="Math enthusiasts",
        semester=semester,
        is_club=True,
    )
    club2 = Course.objects.create(
        name="Chess Club",
        description="Chess players",
        semester=semester,
        is_club=True,
    )

    # Create attendance for different clubs on same date
    Attendance.objects.create(user=user, date=date.today(), club=club1)
    Attendance.objects.create(user=user, date=date.today(), club=club2)

    assert Attendance.objects.filter(user=user, date=date.today()).count() == 2
