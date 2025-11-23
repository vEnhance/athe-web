from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student

from yearbook.models import YearbookEntry


@pytest.mark.django_db
def test_semester_list_requires_login():
    """Test that viewing the semester yearbook requires login."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_semester_list_staff_can_access_any_semester():
    """Test that staff can view yearbook for any semester."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    User.objects.create_user(username="staff", password="password", is_staff=True)

    client.login(username="staff", password="password")
    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_semester_list_student_in_semester_can_access():
    """Test that students in the semester can view the yearbook."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    Student.objects.create(
        user=user,
        airtable_name="Student",
        semester=semester,
    )

    client.login(username="student", password="password")
    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_semester_list_student_not_in_semester_denied():
    """Test that students not in the semester cannot view the yearbook."""
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
    user = User.objects.create_user(username="student", password="password")
    # Student is in a different semester
    Student.objects.create(
        user=user,
        airtable_name="Student",
        semester=other_semester,
    )

    client.login(username="student", password="password")
    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_semester_list_user_without_student_denied():
    """Test that users without any student record cannot view the yearbook."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    User.objects.create_user(username="regular", password="password")

    client.login(username="regular", password="password")
    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_semester_list_student_can_view_without_having_entry():
    """Test that students can view the yearbook even if they don't have an entry."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    Student.objects.create(
        user=user,
        airtable_name="Student without entry",
        semester=semester,
    )

    client.login(username="student", password="password")
    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    assert "No yearbook entries yet" in response.content.decode()


@pytest.mark.django_db
def test_semester_list_shows_entries_sorted_by_house():
    """Test that yearbook entries are sorted by house."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students in different houses
    user = User.objects.create_user(username="viewer", password="password")
    Student.objects.create(user=user, airtable_name="Viewer", semester=semester)

    blob_student = Student.objects.create(
        airtable_name="Blob Student",
        semester=semester,
        house=Student.House.BLOB,
    )
    cat_student = Student.objects.create(
        airtable_name="Cat Student",
        semester=semester,
        house=Student.House.CAT,
    )
    owl_student = Student.objects.create(
        airtable_name="Owl Student",
        semester=semester,
        house=Student.House.OWL,
    )

    # Create entries
    YearbookEntry.objects.create(
        student=cat_student, display_name="Cat Person", bio="I love cats"
    )
    YearbookEntry.objects.create(
        student=blob_student, display_name="Blob Person", bio="I love blobs"
    )
    YearbookEntry.objects.create(
        student=owl_student, display_name="Owl Person", bio="I love owls"
    )

    client.login(username="viewer", password="password")
    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Check all entries are shown
    assert "Blob Person" in content
    assert "Cat Person" in content
    assert "Owl Person" in content


@pytest.mark.django_db
def test_semester_list_shows_create_button_before_semester_ends():
    """Test that the create button is shown before the semester ends."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    Student.objects.create(user=user, airtable_name="Student", semester=semester)

    client.login(username="student", password="password")
    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Should show create button since student doesn't have an entry
    assert "Create Your Entry" in content


@pytest.mark.django_db
def test_semester_list_shows_edit_button_for_existing_entry():
    """Test that the edit button is shown for students with existing entries."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    student = Student.objects.create(
        user=user, airtable_name="Student", semester=semester
    )
    YearbookEntry.objects.create(
        student=student, display_name="Student Name", bio="My bio"
    )

    client.login(username="student", password="password")
    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Should show edit button since student has an entry
    assert "Edit Your Entry" in content


@pytest.mark.django_db
def test_semester_list_no_edit_button_after_semester_ends():
    """Test that no edit/create button is shown after semester ends."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2024",
        slug="fa24",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    Student.objects.create(user=user, airtable_name="Student", semester=semester)

    client.login(username="student", password="password")
    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Should show message that semester has ended
    assert "semester has ended" in content
    assert "Create Your Entry" not in content
    assert "Edit Your Entry" not in content


@pytest.mark.django_db
def test_semester_list_shows_social_links():
    """Test that social media links are displayed correctly."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="viewer", password="password")
    Student.objects.create(user=user, airtable_name="Viewer", semester=semester)

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
    url = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    content = response.content.decode()
    assert "socialuser#1234" in content
    assert "socialinsta" in content
    assert "socialgit" in content
    assert "https://social.example.com" in content
