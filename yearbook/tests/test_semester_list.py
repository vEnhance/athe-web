from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student


@pytest.mark.django_db
def test_semester_list_view_requires_login():
    """Test that viewing the semester list requires login."""
    client = Client()
    url = reverse("yearbook:semester_list")
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_semester_list_view_shows_all_semesters():
    """Test that the semester list shows all semesters for staff."""
    client = Client()
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    spring = Semester.objects.create(
        name="Spring 2025",
        slug="sp25",
        start_date=(timezone.now() - timedelta(days=180)).date(),
        end_date=(timezone.now() - timedelta(days=90)).date(),
    )
    User.objects.create_user(username="staffuser", password="password", is_staff=True)
    client.login(username="staffuser", password="password")
    url = reverse("yearbook:semester_list")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Fall 2025" in content
    assert "Spring 2025" in content

    studentuser = User.objects.create_user(username="studentuser", password="password")
    Student.objects.create(semester=spring, user=studentuser)
    client.login(username="studentuser", password="password")
    url = reverse("yearbook:semester_list")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Fall 2025" not in content
    assert "Spring 2025" in content


@pytest.mark.django_db
def test_semester_list_view_empty_state():
    """Test that the semester list shows a message when no semesters exist."""
    client = Client()
    User.objects.create_user(username="user", password="password")

    client.login(username="user", password="password")
    url = reverse("yearbook:semester_list")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "No semesters available" in content
