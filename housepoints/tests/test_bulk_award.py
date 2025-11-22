from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student
from housepoints.models import Award

# ============================================================================
# Bulk Award View Tests
# ============================================================================


@pytest.mark.django_db
def test_bulk_award_requires_staff():
    """Test that bulk award view requires staff access."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    client.login(username="student", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.get(url)

    # Should be forbidden (403)
    assert response.status_code == 403


@pytest.mark.django_db
def test_bulk_award_staff_access():
    """Test that staff can access bulk award view."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    # Create an active semester
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.get(url)

    assert response.status_code == 200
    assert "Bulk Award Points" in response.content.decode()


@pytest.mark.django_db
def test_bulk_award_creates_awards():
    """Test that bulk award successfully creates awards for multiple users."""
    client = Client()
    staff = User.objects.create_user(
        username="staff", password="password", is_staff=True
    )
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students
    user1 = User.objects.create_user(
        username="alice", password="password", email="alice@example.com"
    )
    user2 = User.objects.create_user(
        username="bob", password="password", email="bob@example.com"
    )
    Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    Student.objects.create(
        user=user2,
        semester=semester,
        house=Student.House.CAT,
        airtable_name="Bob Jones",
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "award_type": Award.AwardType.OFFICE_HOURS,
            "airtable_names": "Alice Smith\nBob Jones",
            "points": "",  # Use default
            "description": "Week 1 OH",
        },
    )

    assert response.status_code == 200
    # Check awards were created
    assert Award.objects.count() == 2
    alice_award = Award.objects.get(student__user__username="alice")
    assert alice_award.points == 2  # Default for office hours
    assert alice_award.house == "owl"
    assert alice_award.awarded_by == staff

    bob_award = Award.objects.get(student__user__username="bob")
    assert bob_award.points == 2
    assert bob_award.house == "cat"


@pytest.mark.django_db
def test_bulk_award_custom_points():
    """Test that bulk award can use custom point values."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    user = User.objects.create_user(
        username="alice", password="password", email="alice@example.com"
    )
    Student.objects.create(
        user=user, semester=semester, house=Student.House.BLOB, airtable_name="Alice"
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "award_type": Award.AwardType.CLASS_ATTENDANCE,
            "airtable_names": "Alice",
            "points": "3",  # Custom points (e.g., for subsequent classes)
            "description": "Week 15 attendance",
        },
    )

    assert response.status_code == 200
    award = Award.objects.get(student__user__username="alice")
    assert award.points == 3


@pytest.mark.django_db
def test_bulk_award_handles_missing_student():
    """Test that bulk award handles non-existent students gracefully."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    user = User.objects.create_user(
        username="alice", password="password", email="alice@example.com"
    )
    Student.objects.create(
        user=user, semester=semester, house=Student.House.OWL, airtable_name="Alice"
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "award_type": Award.AwardType.HOMEWORK,
            "airtable_names": "Alice\nNonexistent Student",
            "points": "",
            "description": "",
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    # Alice should succeed
    assert "Alice" in content
    # Nonexistent should fail
    assert "Nonexistent Student" in content
    assert "Not enrolled" in content or "not enrolled" in content.lower()
    # Only one award should be created
    assert Award.objects.count() == 1


@pytest.mark.django_db
def test_bulk_award_handles_student_without_house():
    """Test that bulk award handles students without house assignment."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    user = User.objects.create_user(
        username="alice", password="password", email="alice@example.com"
    )
    Student.objects.create(
        user=user, semester=semester, house="", airtable_name="Alice"
    )  # No house

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "award_type": Award.AwardType.HOMEWORK,
            "airtable_names": "Alice",
            "points": "",
            "description": "",
        },
    )

    content = response.content.decode()
    assert "No house assigned" in content
    assert Award.objects.count() == 0


@pytest.mark.django_db
def test_bulk_award_no_active_semester():
    """Test that bulk award fails gracefully when no active semester exists."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    # Create a past semester
    Semester.objects.create(
        name="Spring 2020",
        slug="sp20",
        start_date=(timezone.now() - timedelta(days=200)).date(),
        end_date=(timezone.now() - timedelta(days=110)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.get(url)

    # Should redirect to home with error message
    assert response.status_code == 302
    assert response.url == reverse("home:index")


@pytest.mark.django_db
def test_bulk_award_multiple_active_semesters():
    """Test that bulk award fails when multiple overlapping semesters exist."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    # Create two overlapping semesters
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=10)).date(),
        end_date=(timezone.now() + timedelta(days=80)).date(),
    )
    Semester.objects.create(
        name="Winter 2025",
        slug="wi25",
        start_date=(timezone.now() - timedelta(days=5)).date(),
        end_date=(timezone.now() + timedelta(days=85)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.get(url)

    # Should redirect to home with error message
    assert response.status_code == 302
    assert response.url == reverse("home:index")
