from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from courses.models import Semester, Student

from yearbook.models import YearbookEntry


@pytest.mark.django_db
def test_yearbook_entry_creation():
    """Test creating a yearbook entry."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="testuser", password="password")
    student = Student.objects.create(
        user=user,
        airtable_name="Test Student",
        semester=semester,
        house=Student.House.BLOB,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test Display Name",
        bio="This is my bio!",
    )

    assert entry.display_name == "Test Display Name"
    assert entry.bio == "This is my bio!"
    assert entry.student == student
    assert str(entry) == "Test Display Name (Fall 2025)"


@pytest.mark.django_db
def test_yearbook_entry_with_social_links():
    """Test creating a yearbook entry with social media links."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        airtable_name="Social Student",
        semester=semester,
        house=Student.House.CAT,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Social User",
        bio="I love social media!",
        discord_username="socialuser#1234",
        instagram_username="socialuser",
        github_username="socialuser",
        website_url="https://socialuser.com",
    )

    assert entry.discord_username == "socialuser#1234"
    assert entry.instagram_username == "socialuser"
    assert entry.github_username == "socialuser"
    assert entry.website_url == "https://socialuser.com"
