from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student

from yearbook.models import YearbookEntry


@pytest.mark.django_db
def test_detail_view_requires_login():
    """Test that viewing a yearbook entry detail requires login."""
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
        display_name="Test Name",
        bio="Test bio",
    )

    url = reverse("yearbook:entry_detail", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_detail_view_staff_can_access_any_entry():
    """Test that staff can view any yearbook entry."""
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
        display_name="Test Name",
        bio="Test bio",
    )
    User.objects.create_user(username="staff", password="password", is_staff=True)

    client.login(username="staff", password="password")
    url = reverse("yearbook:entry_detail", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert "Test Name" in response.content.decode()


@pytest.mark.django_db
def test_detail_view_student_in_semester_can_access():
    """Test that students in the same semester can view the entry."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    # Student with entry
    entry_student = Student.objects.create(
        airtable_name="Entry Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=entry_student,
        display_name="Entry Person",
        bio="This is my bio",
    )
    # Viewer student in same semester
    viewer = User.objects.create_user(username="viewer", password="password")
    Student.objects.create(
        user=viewer,
        airtable_name="Viewer Student",
        semester=semester,
    )

    client.login(username="viewer", password="password")
    url = reverse("yearbook:entry_detail", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert "Entry Person" in response.content.decode()
    assert "This is my bio" in response.content.decode()


@pytest.mark.django_db
def test_detail_view_student_not_in_semester_denied():
    """Test that students in a different semester cannot view the entry."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    other_semester = Semester.objects.create(
        name="Spring 2025",
        slug="sp25",
        start_date=(timezone.now() - timedelta(days=180)).date(),
        end_date=(timezone.now() - timedelta(days=90)).date(),
    )
    # Entry in fall semester
    entry_student = Student.objects.create(
        airtable_name="Entry Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=entry_student,
        display_name="Entry Person",
        bio="This is my bio",
    )
    # Viewer in different semester
    viewer = User.objects.create_user(username="viewer", password="password")
    Student.objects.create(
        user=viewer,
        airtable_name="Viewer Student",
        semester=other_semester,
    )

    client.login(username="viewer", password="password")
    url = reverse("yearbook:entry_detail", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_detail_view_user_without_student_denied():
    """Test that users without a student record cannot view the entry."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    entry_student = Student.objects.create(
        airtable_name="Entry Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=entry_student,
        display_name="Entry Person",
        bio="This is my bio",
    )
    User.objects.create_user(username="regular", password="password")

    client.login(username="regular", password="password")
    url = reverse("yearbook:entry_detail", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_detail_view_shows_full_bio():
    """Test that the detail view shows the full bio, not truncated."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    # Long bio that would be truncated in list view
    long_bio = "This is a very long biography. " * 20
    entry_student = Student.objects.create(
        airtable_name="Entry Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=entry_student,
        display_name="Entry Person",
        bio=long_bio,
    )
    viewer = User.objects.create_user(username="viewer", password="password")
    Student.objects.create(
        user=viewer,
        airtable_name="Viewer Student",
        semester=semester,
    )

    client.login(username="viewer", password="password")
    url = reverse("yearbook:entry_detail", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Full bio should be shown (the truncatechars filter adds "..." which wouldn't be in full)
    assert long_bio[:200] in content


@pytest.mark.django_db
def test_detail_view_shows_social_links():
    """Test that social media links are displayed correctly in detail view."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    viewer = User.objects.create_user(username="viewer", password="password")
    Student.objects.create(user=viewer, airtable_name="Viewer", semester=semester)

    student = Student.objects.create(
        airtable_name="Social Student",
        semester=semester,
        house=Student.House.BLOB,
    )
    YearbookEntry.objects.create(
        student=student,
        display_name="Social Person",
        bio="Check out my socials!",
        discord_username="socialuser#1234",
        instagram_username="socialinsta",
        github_username="socialgit",
        website_url="https://social.example.com",
    )

    client.login(username="viewer", password="password")
    entry = YearbookEntry.objects.get(student=student)
    url = reverse("yearbook:entry_detail", kwargs={"pk": entry.pk})
    response = client.get(url)

    content = response.content.decode()
    assert "socialuser#1234" in content
    assert "socialinsta" in content
    assert "socialgit" in content
    assert "https://social.example.com" in content


@pytest.mark.django_db
def test_detail_view_shows_house():
    """Test that the house is displayed in the detail view."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    viewer = User.objects.create_user(username="viewer", password="password")
    Student.objects.create(user=viewer, airtable_name="Viewer", semester=semester)

    student = Student.objects.create(
        airtable_name="Owl Student",
        semester=semester,
        house=Student.House.OWL,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Owl Person",
        bio="I love owls!",
    )

    client.login(username="viewer", password="password")
    url = reverse("yearbook:entry_detail", kwargs={"pk": entry.pk})
    response = client.get(url)

    content = response.content.decode()
    assert "Owl" in content


@pytest.mark.django_db
def test_detail_view_has_back_link():
    """Test that the detail view has a link back to the yearbook list."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    viewer = User.objects.create_user(username="viewer", password="password")
    Student.objects.create(user=viewer, airtable_name="Viewer", semester=semester)

    student = Student.objects.create(
        airtable_name="Test Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test Person",
        bio="Test bio",
    )

    client.login(username="viewer", password="password")
    url = reverse("yearbook:entry_detail", kwargs={"pk": entry.pk})
    response = client.get(url)

    content = response.content.decode()
    back_url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    assert back_url in content


@pytest.mark.django_db
def test_detail_view_nonexistent_entry_returns_404():
    """Test that requesting a non-existent entry returns 404."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    client.login(username="staff", password="password")
    url = reverse("yearbook:entry_detail", kwargs={"pk": 99999})
    response = client.get(url)

    assert response.status_code == 404
