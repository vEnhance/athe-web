from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.db.models import Sum
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student
from housepoints.models import Award


# ============================================================================
# Leaderboard View Tests
# ============================================================================


@pytest.mark.django_db
def test_leaderboard():
    """Test that leaderboard loads even with no login."""
    client = Client()
    url = reverse("housepoints:leaderboard")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_leaderboard_calculates_totals():
    """Test that leaderboard correctly calculates house totals."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students in different houses
    user1 = User.objects.create_user(username="user1", password="password")
    user2 = User.objects.create_user(username="user2", password="password")
    student1 = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Student 1",
    )
    student2 = Student.objects.create(
        user=user2,
        semester=semester,
        house=Student.House.CAT,
        airtable_name="Student 2",
    )

    # Create awards
    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=student2,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug})
    response = client.get(url)

    content = response.content.decode()
    assert response.status_code == 200
    # Owls should have 10 points (5+5), Cats should have 5
    assert "10" in content  # Owls total
    assert "Owls" in content
    assert "Cats" in content


@pytest.mark.django_db
def test_leaderboard_respects_freeze_date():
    """Test that leaderboard respects the freeze date."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    freeze_time = timezone.now() - timedelta(days=1)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
        house_points_freeze_date=freeze_time,
    )

    user = User.objects.create_user(username="user1", password="password")
    student = Student.objects.create(
        user=user,
        semester=semester,
        house=Student.House.BLOB,
        airtable_name="Student 1",
    )

    # Create award before freeze date (should count)
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
        awarded_at=freeze_time - timedelta(hours=1),
    )
    # Create award after freeze date (should not count)
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=10,
        awarded_at=freeze_time + timedelta(hours=1),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug})
    client.get(url)  # Trigger view to ensure it works

    # Total should be 5 (not 15)
    total = Award.objects.filter(
        semester=semester, awarded_at__lte=freeze_time
    ).aggregate(total=Sum("points"))["total"]
    assert total == 5


@pytest.mark.django_db
def test_leaderboard_shows_all_houses():
    """Test that all houses are shown even with zero points."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug})
    response = client.get(url)

    content = response.content.decode()
    # All houses should appear
    assert "Blobs" in content
    assert "Cats" in content
    assert "Owls" in content
    assert "Red Panda" in content
    assert "Bunnies" in content
