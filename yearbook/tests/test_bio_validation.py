from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student

from yearbook.models import YearbookEntry


@pytest.mark.django_db
def test_bio_max_length_validation():
    """Test that bio is limited to 1000 characters."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:create", kwargs={"student_pk": student.pk})

    # Try to submit a bio that's too long
    long_bio = "x" * 1001
    response = client.post(
        url,
        {
            "display_name": "Test Name",
            "bio": long_bio,
            "discord_username": "",
            "instagram_username": "",
            "github_username": "",
            "website_url": "",
        },
    )

    # Should not redirect (form error)
    assert response.status_code == 200
    # Entry should not be created
    assert not YearbookEntry.objects.filter(student=student).exists()


@pytest.mark.django_db
def test_bio_at_max_length_succeeds():
    """Test that a bio at exactly 1000 characters is accepted."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:create", kwargs={"student_pk": student.pk})

    # Submit a bio at exactly 1000 characters
    max_bio = "x" * 1000
    response = client.post(
        url,
        {
            "display_name": "Test Name",
            "bio": max_bio,
            "discord_username": "",
            "instagram_username": "",
            "github_username": "",
            "website_url": "",
        },
    )

    # Should redirect on success
    assert response.status_code == 302
    # Entry should be created
    entry = YearbookEntry.objects.get(student=student)
    assert len(entry.bio) == 1000
