from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student

# ============================================================================
# Navigation Tests
# ============================================================================


@pytest.fixture
def semester():
    return Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date() - timedelta(days=1),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )


@pytest.mark.django_db
def test_dashboard_house_links_for_student(semester: Semester):
    """House points links live on the dashboard now, not in the navbar."""
    client = Client()
    user = User.objects.create_user(username="user", password="password")
    Student.objects.create(
        user=user,
        semester=semester,
        house=Student.House.BUNNY,
        airtable_name="Student",
    )

    client.login(username="user", password="password")
    response = client.get(reverse("index"))

    content = response.content.decode()
    assert "Bunnies" in content
    assert (
        reverse("housepoints:leaderboard_semester", kwargs={"slug": "fa25"}) in content
    )
    assert reverse("housepoints:my_awards") in content


@pytest.mark.django_db
def test_dashboard_bulk_award_link_for_staff():
    """Test that Award Points link appears for staff only."""
    client = Client()
    User.objects.create_user(username="user", password="password")
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Regular user should not see Award Points link
    client.login(username="user", password="password")
    response = client.get(reverse("index"))
    content = response.content.decode()
    assert "Award Points" not in content

    # Staff should see Award Points link
    client.login(username="staff", password="password")
    response = client.get(reverse("index"))
    content = response.content.decode()
    assert "Award Points" in content
