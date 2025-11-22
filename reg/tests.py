from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student
from home.models import StaffPhotoListing

from .models import StaffInviteLink, StudentInviteLink


@pytest.mark.django_db
def test_create_invite_link():
    """Test creating a staff invite link."""
    future_date = timezone.now() + timedelta(days=7)
    invite = StaffInviteLink.objects.create(
        name="Test Invite",
        expiration_date=future_date,
    )
    assert invite.id is not None
    assert invite.name == "Test Invite"
    assert invite.is_expired() is False


@pytest.mark.django_db
def test_is_expired_future_date():
    """Test that future dates are not expired."""
    future_date = timezone.now() + timedelta(days=7)
    invite = StaffInviteLink.objects.create(
        name="Future Invite",
        expiration_date=future_date,
    )
    assert invite.is_expired() is False


@pytest.mark.django_db
def test_is_expired_past_date():
    """Test that past dates are expired."""
    past_date = timezone.now() - timedelta(days=7)
    invite = StaffInviteLink.objects.create(
        name="Past Invite",
        expiration_date=past_date,
    )
    assert invite.is_expired() is True


@pytest.mark.django_db
def test_get_absolute_url():
    """Test the get_absolute_url method."""
    future_date = timezone.now() + timedelta(days=7)
    invite = StaffInviteLink.objects.create(
        name="Test Invite",
        expiration_date=future_date,
    )
    url = invite.get_absolute_url()
    assert url == reverse("reg:add-staff", kwargs={"invite_id": invite.id})


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


@pytest.fixture
def student_invite_model_setup():
    """Set up test data for student invite model tests."""
    future_date = timezone.now() + timedelta(days=7)
    past_date = timezone.now() - timedelta(days=7)

    # Create semesters
    active_semester = Semester.objects.create(
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

    return {
        "future_date": future_date,
        "past_date": past_date,
        "active_semester": active_semester,
        "ended_semester": ended_semester,
    }


@pytest.mark.django_db
def test_create_student_invite_link(student_invite_model_setup):
    """Test creating a student invite link."""
    invite = StudentInviteLink.objects.create(
        name="Test Invite",
        semester=student_invite_model_setup["active_semester"],
        expiration_date=student_invite_model_setup["future_date"],
    )
    assert invite.id is not None
    assert invite.name == "Test Invite"
    assert invite.semester == student_invite_model_setup["active_semester"]
    assert invite.is_expired() is False
    assert invite.is_semester_ended() is False


@pytest.mark.django_db
def test_student_invite_is_expired_future_date(student_invite_model_setup):
    """Test that future dates are not expired."""
    invite = StudentInviteLink.objects.create(
        name="Future Invite",
        semester=student_invite_model_setup["active_semester"],
        expiration_date=student_invite_model_setup["future_date"],
    )
    assert invite.is_expired() is False


@pytest.mark.django_db
def test_student_invite_is_expired_past_date(student_invite_model_setup):
    """Test that past dates are expired."""
    invite = StudentInviteLink.objects.create(
        name="Past Invite",
        semester=student_invite_model_setup["active_semester"],
        expiration_date=student_invite_model_setup["past_date"],
    )
    assert invite.is_expired() is True


@pytest.mark.django_db
def test_is_semester_ended_active_semester(student_invite_model_setup):
    """Test that active semester is not ended."""
    invite = StudentInviteLink.objects.create(
        name="Active Semester Invite",
        semester=student_invite_model_setup["active_semester"],
        expiration_date=student_invite_model_setup["future_date"],
    )
    assert invite.is_semester_ended() is False


@pytest.mark.django_db
def test_is_semester_ended_past_semester(student_invite_model_setup):
    """Test that past semester is ended."""
    invite = StudentInviteLink.objects.create(
        name="Ended Semester Invite",
        semester=student_invite_model_setup["ended_semester"],
        expiration_date=student_invite_model_setup["future_date"],
    )
    assert invite.is_semester_ended() is True


@pytest.mark.django_db
def test_student_invite_get_absolute_url(student_invite_model_setup):
    """Test the get_absolute_url method."""
    invite = StudentInviteLink.objects.create(
        name="Test Invite",
        semester=student_invite_model_setup["active_semester"],
        expiration_date=student_invite_model_setup["future_date"],
    )
    url = invite.get_absolute_url()
    assert url == reverse("reg:add-student", kwargs={"invite_id": invite.id})


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


# Remaining converted tests for student invite views


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
