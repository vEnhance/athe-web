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


@pytest.mark.django_db
def test_admin_add_and_change_pages_render():
    """Both invite admins render their add and change forms with fieldsets."""
    client = Client()
    User.objects.create_superuser(
        username="admin", password="admin123", email="admin@example.com"
    )
    client.login(username="admin", password="admin123")

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fall-2025",
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timedelta(days=30),
    )
    staff_invite = StaffInviteLink.objects.create(
        name="Staff invite", expiration_date=timezone.now() + timedelta(days=5)
    )
    student_invite = StudentInviteLink.objects.create(
        name="Student invite",
        semester=semester,
        expiration_date=timezone.now() + timedelta(days=5),
    )

    for model, invite in (
        ("staffinvitelink", staff_invite),
        ("studentinvitelink", student_invite),
    ):
        assert client.get(reverse(f"admin:reg_{model}_add")).status_code == 200
        response = client.get(reverse(f"admin:reg_{model}_change", args=[invite.pk]))
        assert response.status_code == 200
        body = response.content.decode()
        assert "Link Information" in body
        assert invite.get_absolute_url() in body

    # The student admin adds semester to the editable fieldset
    response = client.get(
        reverse("admin:reg_studentinvitelink_change", args=[student_invite.pk])
    )
    assert "Semester" in response.content.decode()
