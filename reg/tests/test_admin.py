from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester

from reg.models import StaffInviteLink, StudentInviteLink


@pytest.mark.django_db
def test_admin_list_display():
    """Test that admin list page works."""
    client = Client()
    # Create admin user
    User.objects.create_superuser(
        username="admin",
        password="admin123",
        email="admin@example.com",
    )
    client.login(username="admin", password="admin123")

    url = reverse("admin:reg_staffinvitelink_changelist")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_admin_create_invite():
    """Test creating invite link through admin."""
    client = Client()
    # Create admin user
    User.objects.create_superuser(
        username="admin",
        password="admin123",
        email="admin@example.com",
    )
    client.login(username="admin", password="admin123")

    url = reverse("admin:reg_staffinvitelink_add")
    response = client.post(
        url,
        {
            "name": "New Invite",
            "expiration_date_0": "2025-12-31",  # Date part
            "expiration_date_1": "23:59:59",  # Time part
        },
    )
    # Should redirect to changelist on success
    assert response.status_code == 302

    # Check invite was created
    invite = StaffInviteLink.objects.get(name="New Invite")
    assert invite is not None


@pytest.mark.django_db
def test_student_admin_list_display():
    """Test that admin list page works."""
    client = Client()
    User.objects.create_superuser(
        username="admin",
        password="admin123",
        email="admin@example.com",
    )
    client.login(username="admin", password="admin123")

    url = reverse("admin:reg_studentinvitelink_changelist")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_student_admin_create_invite():
    """Test creating invite link through admin."""
    client = Client()
    User.objects.create_superuser(
        username="admin",
        password="admin123",
        email="admin@example.com",
    )
    client.login(username="admin", password="admin123")

    # Create semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fall-2025",
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timedelta(days=90),
    )

    url = reverse("admin:reg_studentinvitelink_add")
    response = client.post(
        url,
        {
            "name": "New Student Invite",
            "semester": semester.id,
            "expiration_date_0": "2025-12-31",  # Date part
            "expiration_date_1": "23:59:59",  # Time part
        },
    )
    # Should redirect to changelist on success
    assert response.status_code == 302

    # Check invite was created
    invite = StudentInviteLink.objects.get(name="New Student Invite")
    assert invite is not None
    assert invite.semester == semester
