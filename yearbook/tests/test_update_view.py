from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student

from yearbook.models import YearbookEntry


@pytest.mark.django_db
def test_update_view_requires_login():
    """Test that updating a yearbook entry requires login."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        airtable_name="Test Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test",
        bio="Test bio",
    )

    url = reverse("yearbook:edit", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_update_view_only_owner_can_access():
    """Test that only the student's user can update their yearbook entry."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    User.objects.create_user(username="other", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test",
        bio="Test bio",
    )

    # Other user tries to access
    client.login(username="other", password="password")
    url = reverse("yearbook:edit", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_update_view_owner_can_access():
    """Test that the student's owner can access the update view."""
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
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test",
        bio="Test bio",
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:edit", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_update_view_denied_after_semester_ended():
    """Test that yearbook entries cannot be updated after semester ends."""
    client = Client()
    # Create a semester that has ended
    semester = Semester.objects.create(
        name="Fall 2024",
        slug="fa24",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test",
        bio="Test bio",
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:edit", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_update_view_successful_submission():
    """Test successfully updating a yearbook entry."""
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
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Old Name",
        bio="Old bio",
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:edit", kwargs={"pk": entry.pk})
    response = client.post(
        url,
        {
            "display_name": "New Name",
            "bio": "New bio with more content!",
            "discord_username": "newuser#5678",
            "instagram_username": "newinstagram",
            "github_username": "",
            "website_url": "",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "yearbook:entry_list", kwargs={"slug": semester.slug}
    )

    # Verify entry was updated
    entry.refresh_from_db()
    assert entry.display_name == "New Name"
    assert entry.bio == "New bio with more content!"
    assert entry.discord_username == "newuser#5678"
    assert entry.instagram_username == "newinstagram"
