from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student
from housepoints.models import Award

#
# ============================================================================
# My Awards View Tests
# ============================================================================


@pytest.mark.django_db
def test_my_awards_requires_login():
    """Test that my awards page requires authentication."""
    client = Client()
    url = reverse("housepoints:my_awards")
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_my_awards_shows_user_awards():
    """Test that my awards page shows the user's awards."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.BUNNY, airtable_name="Student"
    )

    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.INTRO_POST,
        points=1,
        description="Posted intro",
    )

    client.login(username="student", password="password")
    url = reverse("housepoints:my_awards")
    response = client.get(url)

    content = response.content.decode()
    assert response.status_code == 200
    assert "Introduction Post" in content
    assert "+1" in content


@pytest.mark.django_db
def test_my_awards_shows_semester_totals():
    """Test that my awards page shows totals per semester."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.CAT, airtable_name="Student"
    )

    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )

    client.login(username="student", password="password")
    url = reverse("housepoints:my_awards")
    response = client.get(url)

    content = response.content.decode()
    assert "10" in content  # Total points
    assert "Cats" in content  # House name


@pytest.mark.django_db
def test_my_awards_only_shows_own_awards():
    """Test that users only see their own awards."""
    client = Client()
    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student1 = Student.objects.create(
        user=user1, semester=semester, house=Student.House.OWL, airtable_name="Alice"
    )
    student2 = Student.objects.create(
        user=user2, semester=semester, house=Student.House.CAT, airtable_name="Bob"
    )

    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.POTD,
        points=20,
        description="Alice PotD",
    )
    Award.objects.create(
        semester=semester,
        student=student2,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
        description="Bob HW",
    )

    # Login as Alice
    client.login(username="alice", password="password")
    url = reverse("housepoints:my_awards")
    response = client.get(url)

    content = response.content.decode()
    assert "Problem of the Day" in content
    assert "Homework" not in content
