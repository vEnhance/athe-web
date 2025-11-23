from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester
from home.models import StaffPhotoListing

from reg.models import StaffInviteLink


@pytest.fixture
def staff_invite_setup():
    """Set up test data for staff invite tests."""
    # Create staff photo listings
    staff1 = StaffPhotoListing.objects.create(
        display_name="John Doe",
        slug="john-doe",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        ordering=0,
    )
    staff2 = StaffPhotoListing.objects.create(
        display_name="Jane Smith",
        slug="jane-smith",
        role="TA",
        category="ta",
        biography="Test bio",
        ordering=0,
    )

    # Create a user and link to staff2
    existing_user = User.objects.create_user(
        username="janesmith",
        password="testpass123",
        email="jane@example.com",
        first_name="Jane",
        last_name="Smith",
        is_staff=True,
    )
    staff2.user = existing_user
    staff2.save()

    # Create invite links
    valid_invite = StaffInviteLink.objects.create(
        name="Valid Invite",
        expiration_date=timezone.now() + timedelta(days=7),
    )
    expired_invite = StaffInviteLink.objects.create(
        name="Expired Invite",
        expiration_date=timezone.now() - timedelta(days=7),
    )

    # Create a semester and course
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fall-2025",
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timedelta(days=90),
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test course description",
        semester=semester,
        instructor=staff1,
    )

    return {
        "staff1": staff1,
        "staff2": staff2,
        "existing_user": existing_user,
        "valid_invite": valid_invite,
        "expired_invite": expired_invite,
        "semester": semester,
        "course": course,
    }


@pytest.mark.django_db
def test_get_staff_selection(staff_invite_setup):
    """Test GET request shows staff selection form."""
    client = Client()
    url = reverse(
        "reg:add-staff", kwargs={"invite_id": staff_invite_setup["valid_invite"].id}
    )
    response = client.get(url)
    assert response.status_code == 200
    assert "John Doe" in response.content.decode()
    assert "Jane Smith" in response.content.decode()


@pytest.mark.django_db
def test_get_expired_invite(staff_invite_setup):
    """Test GET request to expired invite shows error."""
    client = Client()
    url = reverse(
        "reg:add-staff", kwargs={"invite_id": staff_invite_setup["expired_invite"].id}
    )
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_post_staff_selection(staff_invite_setup):
    """Test POST request to select staff listing."""
    client = Client()
    url = reverse(
        "reg:add-staff", kwargs={"invite_id": staff_invite_setup["valid_invite"].id}
    )
    response = client.post(url, {"staff_listing": staff_invite_setup["staff1"].id})
    assert response.status_code == 302  # Redirect
    # Check session has staff_listing_id
    session = client.session
    assert session["staff_listing_id"] == staff_invite_setup["staff1"].id


@pytest.mark.django_db
def test_post_staff_selection_already_registered(staff_invite_setup):
    """Test POST request to select already registered staff shows error."""
    client = Client()
    url = reverse(
        "reg:add-staff", kwargs={"invite_id": staff_invite_setup["valid_invite"].id}
    )
    response = client.post(url, {"staff_listing": staff_invite_setup["staff2"].id})
    assert response.status_code == 200
    assert "janesmith" in response.content.decode()


@pytest.mark.django_db
def test_get_registration_form(staff_invite_setup):
    """Test GET request shows registration form when staff is selected."""
    client = Client()
    # Set session
    session = client.session
    session["staff_listing_id"] = staff_invite_setup["staff1"].id
    session.save()

    url = reverse(
        "reg:add-staff", kwargs={"invite_id": staff_invite_setup["valid_invite"].id}
    )
    response = client.get(url)
    assert response.status_code == 200
    assert "John Doe" in response.content.decode()


@pytest.mark.django_db
def test_post_registration_creates_user(staff_invite_setup):
    """Test POST request creates user and links to staff listing."""
    client = Client()
    # Set session
    session = client.session
    session["staff_listing_id"] = staff_invite_setup["staff1"].id
    session.save()

    url = reverse(
        "reg:add-staff", kwargs={"invite_id": staff_invite_setup["valid_invite"].id}
    )
    response = client.post(
        url,
        {
            "username": "johndoe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password1": "testpass123!@#",
            "password2": "testpass123!@#",
        },
    )
    assert response.status_code == 302  # Redirect to home

    # Check user was created
    user = User.objects.get(username="johndoe")
    assert user.is_staff is True
    assert user.email == "john@example.com"
    assert user.first_name == "John"
    assert user.last_name == "Doe"

    # Check staff listing is linked
    staff_invite_setup["staff1"].refresh_from_db()
    assert staff_invite_setup["staff1"].user == user

    # Check user is logged in
    assert response.wsgi_request.user.is_authenticated is True
    assert response.wsgi_request.user.username == "johndoe"

    # Check session is cleared
    session = client.session
    assert "staff_listing_id" not in session


@pytest.mark.django_db
def test_post_registration_adds_user_to_course_leaders(staff_invite_setup):
    """Test that registration adds user to course leaders when they are instructor."""
    client = Client()
    # Set session
    session = client.session
    session["staff_listing_id"] = staff_invite_setup["staff1"].id
    session.save()

    url = reverse(
        "reg:add-staff", kwargs={"invite_id": staff_invite_setup["valid_invite"].id}
    )
    response = client.post(
        url,
        {
            "username": "johndoe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password1": "testpass123!@#",
            "password2": "testpass123!@#",
        },
    )
    assert response.status_code == 302

    # Check user was added to course leaders
    user = User.objects.get(username="johndoe")
    staff_invite_setup["course"].refresh_from_db()
    assert user in staff_invite_setup["course"].leaders.all()


@pytest.mark.django_db
def test_post_registration_invalid_form(staff_invite_setup):
    """Test POST request with invalid form shows errors."""
    client = Client()
    # Set session
    session = client.session
    session["staff_listing_id"] = staff_invite_setup["staff1"].id
    session.save()

    url = reverse(
        "reg:add-staff", kwargs={"invite_id": staff_invite_setup["valid_invite"].id}
    )
    response = client.post(
        url,
        {
            "username": "johndoe",
            "email": "invalid-email",  # Invalid email
            "first_name": "John",
            "last_name": "Doe",
            "password1": "testpass123!@#",
            "password2": "differentpass",  # Passwords don't match
        },
    )
    assert response.status_code == 200
    # User should not be created
    assert User.objects.filter(username="johndoe").exists() is False


@pytest.mark.django_db
def test_session_cleared_when_accessing_already_registered_staff(staff_invite_setup):
    """Test that session is cleared when trying to register already registered staff."""
    client = Client()
    # Set session to staff2 who already has a user
    session = client.session
    session["staff_listing_id"] = staff_invite_setup["staff2"].id
    session.save()

    url = reverse(
        "reg:add-staff", kwargs={"invite_id": staff_invite_setup["valid_invite"].id}
    )
    response = client.get(url)
    assert response.status_code == 200

    # Check session is cleared
    session = client.session
    assert "staff_listing_id" not in session


@pytest.mark.django_db
def test_multiple_courses_with_same_instructor(staff_invite_setup):
    """Test that user is added to all courses where they are instructor."""
    # Create another course with the same instructor
    course2 = Course.objects.create(
        name="Test Course 2",
        description="Test course 2 description",
        semester=staff_invite_setup["semester"],
        instructor=staff_invite_setup["staff1"],
    )

    client = Client()
    # Set session
    session = client.session
    session["staff_listing_id"] = staff_invite_setup["staff1"].id
    session.save()

    url = reverse(
        "reg:add-staff", kwargs={"invite_id": staff_invite_setup["valid_invite"].id}
    )
    response = client.post(
        url,
        {
            "username": "johndoe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "password1": "testpass123!@#",
            "password2": "testpass123!@#",
        },
    )
    assert response.status_code == 302

    # Check user was added to both courses
    user = User.objects.get(username="johndoe")
    staff_invite_setup["course"].refresh_from_db()
    course2.refresh_from_db()
    assert user in staff_invite_setup["course"].leaders.all()
    assert user in course2.leaders.all()
