from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student

from reg.models import StudentInviteLink


@pytest.fixture
def student_invite_view_setup():
    """Set up test data for student invite view tests."""
    # Create semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fall-2025",
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timedelta(days=90),
    )
    ended_semester = Semester.objects.create(
        name="Spring 2024",
        slug="spring-2024",
        start_date=timezone.now().date() - timedelta(days=180),
        end_date=timezone.now().date() - timedelta(days=90),
    )

    # Create students
    student1 = Student.objects.create(
        airtable_name="Alice Johnson",
        semester=semester,
        house=Student.House.BLOB,
    )
    student2 = Student.objects.create(
        airtable_name="Bob Smith",
        semester=semester,
        house=Student.House.CAT,
    )

    # Create a user and link to student2
    existing_user = User.objects.create_user(
        username="bobsmith",
        password="testpass123",
    )
    student2.user = existing_user
    student2.save()

    # Create invite links
    valid_invite = StudentInviteLink.objects.create(
        name="Valid Invite",
        semester=semester,
        expiration_date=timezone.now() + timedelta(days=7),
    )
    expired_invite = StudentInviteLink.objects.create(
        name="Expired Invite",
        semester=semester,
        expiration_date=timezone.now() - timedelta(days=7),
    )
    ended_semester_invite = StudentInviteLink.objects.create(
        name="Ended Semester Invite",
        semester=ended_semester,
        expiration_date=timezone.now() + timedelta(days=7),
    )

    return {
        "semester": semester,
        "ended_semester": ended_semester,
        "student1": student1,
        "student2": student2,
        "existing_user": existing_user,
        "valid_invite": valid_invite,
        "expired_invite": expired_invite,
        "ended_semester_invite": ended_semester_invite,
    }


@pytest.mark.django_db
def test_get_login_choice(student_invite_view_setup):
    """Test GET request shows login choice form when not logged in."""
    client = Client()
    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.get(url)
    assert response.status_code == 200
    assert (
        "Do you already have an account from a previous Athemath?"
        in response.content.decode()
    )


@pytest.mark.django_db
def test_get_expired_invite_student(student_invite_view_setup):
    """Test GET request to expired invite shows error."""
    client = Client()
    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["expired_invite"].id},
    )
    response = client.get(url)
    assert response.status_code == 200
    assert "expired" in response.content.decode()


@pytest.mark.django_db
def test_get_ended_semester_invite(student_invite_view_setup):
    """Test GET request to ended semester invite shows error."""
    client = Client()
    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["ended_semester_invite"].id},
    )
    response = client.get(url)
    assert response.status_code == 200
    assert "semester has ended" in response.content.decode()


@pytest.mark.django_db
def test_post_login_choice_yes(student_invite_view_setup):
    """Test POST request to choose 'yes' redirects to login."""
    client = Client()
    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(url, {"has_account": "yes"})
    assert response.status_code == 302
    # Should redirect to login with next parameter
    assert "/login/" in response.url
    assert "next=" in response.url


@pytest.mark.django_db
def test_post_login_choice_no(student_invite_view_setup):
    """Test POST request to choose 'no' shows registration form."""
    client = Client()
    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(url, {"has_account": "no"})
    assert response.status_code == 302  # Redirect
    # Check session has creating_new_account flag
    session = client.session
    assert session["creating_new_account"] is True


@pytest.mark.django_db
def test_get_registration_form_student(student_invite_view_setup):
    """Test GET request shows registration form when creating new account."""
    client = Client()
    # Set session
    session = client.session
    session["creating_new_account"] = True
    session.save()

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_post_registration_creates_user_student(student_invite_view_setup):
    """Test POST request creates user and redirects to student selection."""
    client = Client()
    # Set session
    session = client.session
    session["creating_new_account"] = True
    session.save()

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(
        url,
        {
            "username": "alicejohnson",
            "password1": "testpass123!@#",
            "password2": "testpass123!@#",
            "email": "alice@example.com",
            "first_name": "Alice",
            "last_name": "Johnson",
        },
    )
    assert response.status_code == 302  # Redirect

    # Check user was created
    user = User.objects.get(username="alicejohnson")
    assert user is not None

    # Check user is logged in
    assert response.wsgi_request.user.is_authenticated is True
    assert response.wsgi_request.user.username == "alicejohnson"

    # Check session flag is cleared
    session = client.session
    assert "creating_new_account" not in session


@pytest.mark.django_db
def test_get_student_selection_as_logged_in_user(student_invite_view_setup):
    """Test GET request shows student selection when logged in."""
    client = Client()
    # Create and login a new user
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.get(url)
    assert response.status_code == 200
    assert "Alice Johnson" in response.content.decode()
    assert "Bob Smith" in response.content.decode()


@pytest.mark.django_db
def test_post_student_selection(student_invite_view_setup):
    """Test POST request to select student links user to student."""
    client = Client()
    # Create and login a new user
    user = User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(url, {"student": student_invite_view_setup["student1"].id})
    assert response.status_code == 302  # Redirect to home

    # Check student is linked to user
    student_invite_view_setup["student1"].refresh_from_db()
    assert student_invite_view_setup["student1"].user == user


@pytest.mark.django_db
def test_post_student_selection_already_taken(student_invite_view_setup):
    """Test POST request to select already taken student shows error."""
    client = Client()
    # Create and login a new user
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(url, {"student": student_invite_view_setup["student2"].id})
    assert response.status_code == 200
    assert "Bob Smith" in response.content.decode()


@pytest.mark.django_db
def test_get_already_registered_student(student_invite_view_setup):
    """Test GET request when user already has student for this semester."""
    client = Client()
    # Login with existing user who already has a student
    client.login(username="bobsmith", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.get(url)
    assert response.status_code == 200
    assert "Bob Smith" in response.content.decode()


@pytest.mark.django_db
def test_post_registration_invalid_form_student(student_invite_view_setup):
    """Test POST request with invalid form shows errors."""
    client = Client()
    # Set session
    session = client.session
    session["creating_new_account"] = True
    session.save()

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(
        url,
        {
            "username": "alicejohnson",
            "password1": "testpass123!@#",
            "password2": "differentpass",  # Passwords don't match
        },
    )
    assert response.status_code == 200
    # User should not be created
    assert User.objects.filter(username="alicejohnson").exists() is False


@pytest.mark.django_db
def test_existing_user_login_flow(student_invite_view_setup):
    """Test that existing users can login and select student."""
    client = Client()
    # Create a user without a student for this semester
    user = User.objects.create_user(username="existinguser", password="testpass123")

    # Get the invite URL
    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )

    # First, choose "yes" (has account)
    response = client.post(url, {"has_account": "yes"})
    assert response.status_code == 302
    assert "/login/" in response.url

    # Login
    client.login(username="existinguser", password="testpass123")

    # Now access the invite link again
    response = client.get(url)
    assert response.status_code == 200

    # Select a student
    response = client.post(url, {"student": student_invite_view_setup["student1"].id})
    assert response.status_code == 302

    # Check student is linked
    student_invite_view_setup["student1"].refresh_from_db()
    assert student_invite_view_setup["student1"].user == user
