from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester

from ta_attendance.models import Attendance


@pytest.mark.django_db
def test_my_attendance_requires_login():
    """Test that my_attendance view requires authentication."""
    client = Client()
    url = reverse("ta_attendance:my_attendance")
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_my_attendance_requires_staff():
    """Test that my_attendance view requires staff status."""
    client = Client()
    User.objects.create_user(username="regular", password="password")

    client.login(username="regular", password="password")
    url = reverse("ta_attendance:my_attendance")
    response = client.get(url)

    # Should redirect with error message
    assert response.status_code == 302
    assert response.url == reverse("home:index")


@pytest.mark.django_db
def test_my_attendance_staff_access():
    """Test that staff can access my_attendance view."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    client.login(username="staff", password="password")
    url = reverse("ta_attendance:my_attendance")
    response = client.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    assert "records" in response.context


@pytest.mark.django_db
def test_my_attendance_shows_only_user_records():
    """Test that my_attendance only shows records for the current user."""
    client = Client()
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

    # Login as user1
    client.login(username="staff1", password="password")
    url = reverse("ta_attendance:my_attendance")
    response = client.get(url)

    # Should only see user1's records
    records = response.context["records"]
    assert len(records) == 1
    assert records[0].user == user1


@pytest.mark.django_db
def test_my_attendance_post_creates_record():
    """Test that POST creates a new attendance record."""
    client = Client()
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
        description="Math",
        semester=semester,
        is_club=True,
    )

    client.login(username="staff", password="password")
    url = reverse("ta_attendance:my_attendance")

    response = client.post(url, {"date": date.today(), "club": club.pk})

    # Should redirect after successful creation
    assert response.status_code == 302
    assert response.url == url

    # Verify record was created
    assert Attendance.objects.filter(user=user, club=club, date=date.today()).exists()


@pytest.mark.django_db
def test_my_attendance_post_duplicate_shows_error():
    """Test that posting a duplicate attendance shows an error."""
    client = Client()
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
        description="Math",
        semester=semester,
        is_club=True,
    )

    # Create existing record
    Attendance.objects.create(user=user, date=date.today(), club=club)

    client.login(username="staff", password="password")
    url = reverse("ta_attendance:my_attendance")

    response = client.post(url, {"date": date.today(), "club": club.pk}, follow=True)

    # Should show error message
    assert response.status_code == 200
    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "already have an attendance record" in str(messages[0])


@pytest.mark.django_db
def test_my_attendance_form_only_shows_active_clubs():
    """Test that the form only shows clubs from semesters that haven't ended."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create active semester
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )
    # Create ended semester
    ended_semester = Semester.objects.create(
        name="Ended Semester",
        slug="ended",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
    )

    active_club = Course.objects.create(
        name="Active Club",
        description="Active",
        semester=active_semester,
        is_club=True,
    )
    Course.objects.create(
        name="Ended Club",
        description="Ended",
        semester=ended_semester,
        is_club=True,
    )

    client.login(username="staff", password="password")
    url = reverse("ta_attendance:my_attendance")
    response = client.get(url)

    form = response.context["form"]
    club_queryset = form.fields["club"].queryset
    club_ids = list(club_queryset.values_list("id", flat=True))

    # Should only contain active club
    assert active_club.id in club_ids
    assert len(club_ids) == 1


@pytest.mark.django_db
def test_my_attendance_form_excludes_non_clubs():
    """Test that the form only shows clubs, not regular courses."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    club = Course.objects.create(
        name="Math Club",
        description="Club",
        semester=semester,
        is_club=True,
    )
    Course.objects.create(
        name="Math 101",
        description="Course",
        semester=semester,
        is_club=False,
    )

    client.login(username="staff", password="password")
    url = reverse("ta_attendance:my_attendance")
    response = client.get(url)

    form = response.context["form"]
    club_queryset = form.fields["club"].queryset
    club_ids = list(club_queryset.values_list("id", flat=True))

    # Should only contain club
    assert club.id in club_ids
    assert len(club_ids) == 1
