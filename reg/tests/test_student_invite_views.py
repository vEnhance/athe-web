from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student
from reg.models import CoursePreference, StudentInviteLink, StudentRegistration


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

    # Create classes to rank, plus a club that has no place in the ranking
    algebra = Course.objects.create(
        name="Algebra", description="Algebra", semester=semester
    )
    geometry = Course.objects.create(
        name="Geometry", description="Geometry", semester=semester
    )
    chess = Course.objects.create(
        name="Chess", description="Chess", semester=semester, is_club=True
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
        "algebra": algebra,
        "geometry": geometry,
        "chess": chess,
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


def questionnaire_post(setup, **overrides):
    """A complete, valid questionnaire submission."""
    data = {
        "student": setup["student1"].id,
        "email": "alice@example.com",
        "parent_email": "parent@example.com",
        "discord_username": "alice",
        "taken_class_before": "no",
        "course_preferences": [setup["geometry"].pk, setup["algebra"].pk],
        "course_comments": "Geometry please!",
        "availability": ["sat-0900", "sat-0930", "sun-1400"],
        "availability_comments": "Busy on Sunday mornings.",
        "quiz_challenge": "plan",
        "quiz_values": "clarity",
        "quiz_compass": "logic",
        "quiz_day_off": "productive",
        "quiz_friend": "trustworthy",
        "house_request": "Owls, like last semester",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_get_questionnaire_as_logged_in_user(student_invite_view_setup):
    """A logged-in user is offered the roster and the questionnaire."""
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Alice Johnson" in content
    assert "Bob Smith" in content
    # Classes are ranked; clubs are joined later and stay out of it.
    assert "Algebra" in content
    assert "Geometry" in content
    assert "Chess" not in content
    assert "How do you usually approach a challenge?" in content


@pytest.mark.django_db
def test_post_questionnaire_binds_user_and_saves_answers(student_invite_view_setup):
    """A valid submission claims the name and stores every answer."""
    client = Client()
    user = User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(url, questionnaire_post(student_invite_view_setup))
    assert response.status_code == 302

    student = student_invite_view_setup["student1"]
    student.refresh_from_db()
    assert student.user == user

    registration = StudentRegistration.objects.get(student=student)
    assert registration.email == "alice@example.com"
    assert registration.parent_email == "parent@example.com"
    assert registration.discord_username == "alice"
    assert registration.taken_class_before is False
    assert registration.availability == ["sat-0900", "sat-0930", "sun-1400"]
    assert registration.quiz_challenge == "plan"
    assert registration.house_request == "Owls, like last semester"

    # Submitted order is the ranking; nothing was excluded.
    ranked = CoursePreference.objects.filter(registration=registration)
    assert [(pref.course.name, pref.rank, pref.excluded) for pref in ranked] == [
        ("Geometry", 1, False),
        ("Algebra", 2, False),
    ]


@pytest.mark.django_db
def test_post_questionnaire_records_excluded_classes(student_invite_view_setup):
    """A class the student rules out is stored as excluded, and unranked."""
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(
        url,
        questionnaire_post(
            student_invite_view_setup,
            course_preferences_excluded=[student_invite_view_setup["geometry"].pk],
        ),
    )
    assert response.status_code == 302

    registration = StudentRegistration.objects.get(
        student=student_invite_view_setup["student1"]
    )
    preferences = {
        pref.course.name: (pref.rank, pref.excluded)
        for pref in CoursePreference.objects.filter(registration=registration)
    }
    assert preferences == {"Geometry": (None, True), "Algebra": (1, False)}


@pytest.mark.django_db
def test_post_questionnaire_rejects_excluding_everything(student_invite_view_setup):
    """Ruling out every class leaves the matching nothing to do."""
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(
        url,
        questionnaire_post(
            student_invite_view_setup,
            course_preferences_excluded=[
                student_invite_view_setup["geometry"].pk,
                student_invite_view_setup["algebra"].pk,
            ],
        ),
    )
    assert response.status_code == 200
    assert response.context["form"].errors["course_preferences"]
    assert not StudentRegistration.objects.exists()
    student_invite_view_setup["student1"].refresh_from_db()
    assert student_invite_view_setup["student1"].user is None


@pytest.mark.django_db
def test_post_questionnaire_requires_availability(student_invite_view_setup):
    """Nothing can be scheduled for a student who marks no time at all."""
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(
        url, questionnaire_post(student_invite_view_setup, availability=[])
    )
    assert response.status_code == 200
    assert response.context["form"].errors["availability"]
    assert not StudentRegistration.objects.exists()


@pytest.mark.django_db
def test_post_questionnaire_rejects_unknown_availability(student_invite_view_setup):
    """Slot keys outside the grid are rejected rather than stored."""
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(
        url, questionnaire_post(student_invite_view_setup, availability=["mon-0300"])
    )
    assert response.status_code == 200
    assert response.context["form"].errors["availability"]


@pytest.mark.django_db
def test_post_questionnaire_already_taken(student_invite_view_setup):
    """Picking a name someone else claimed is refused, form intact."""
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(
        url,
        questionnaire_post(
            student_invite_view_setup, student=student_invite_view_setup["student2"].id
        ),
    )
    assert response.status_code == 200
    assert "already been claimed" in str(response.context["form"].errors["student"])
    assert not StudentRegistration.objects.exists()


@pytest.mark.django_db
def test_registered_student_can_edit_their_answers(student_invite_view_setup):
    """Coming back to the link reopens the questionnaire, filled in."""
    client = Client()
    client.login(username="bobsmith", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Bob Smith" in content
    # The name is settled, so the roster is not offered again.
    assert "Alice Johnson" not in content

    response = client.post(
        url,
        questionnaire_post(
            student_invite_view_setup,
            student="",
            email="bob@example.com",
            availability=["sun-2000"],
        ),
    )
    assert response.status_code == 302

    registration = StudentRegistration.objects.get(
        student=student_invite_view_setup["student2"]
    )
    assert registration.email == "bob@example.com"
    assert registration.availability == ["sun-2000"]

    # Editing again replaces the old ranking instead of adding to it.
    client.post(
        url,
        questionnaire_post(
            student_invite_view_setup,
            student="",
            email="bob@example.com",
            course_preferences=[
                student_invite_view_setup["algebra"].pk,
                student_invite_view_setup["geometry"].pk,
            ],
        ),
    )
    ranked = CoursePreference.objects.filter(registration=registration)
    assert [(pref.course.name, pref.rank) for pref in ranked] == [
        ("Algebra", 1),
        ("Geometry", 2),
    ]
    assert StudentRegistration.objects.count() == 1


@pytest.mark.django_db
def test_post_questionnaire_invalid_student_id(student_invite_view_setup):
    """A non-numeric or unknown student id falls through to form validation."""
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    for bad in ("not-a-number", "999999", ""):
        response = client.post(
            url, questionnaire_post(student_invite_view_setup, student=bad)
        )
        assert response.status_code == 200
        assert response.context["form"].errors["student"]


@pytest.mark.django_db
def test_post_questionnaire_other_semester_student(student_invite_view_setup):
    """A student from another semester is rejected by form validation."""
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    outsider = Student.objects.create(
        airtable_name="Carol Elsewhere",
        semester=student_invite_view_setup["ended_semester"],
    )
    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.post(
        url, questionnaire_post(student_invite_view_setup, student=outsider.pk)
    )
    assert response.status_code == 200
    assert response.context["form"].errors["student"]
    outsider.refresh_from_db()
    assert outsider.user is None


@pytest.mark.django_db
def test_no_students_available(student_invite_view_setup):
    """An empty roster says so rather than showing an empty questionnaire."""
    Student.objects.filter(semester=student_invite_view_setup["semester"]).delete()
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = client.get(url)
    assert response.status_code == 200
    assert "no students" in response.content.decode().lower()


@pytest.mark.django_db
def test_existing_user_login_flow(student_invite_view_setup):
    """Test that existing users can login and fill in the questionnaire."""
    client = Client()
    user = User.objects.create_user(username="existinguser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )

    # First, choose "yes" (has account)
    response = client.post(url, {"has_account": "yes"})
    assert response.status_code == 302
    assert "/login/" in response.url

    client.login(username="existinguser", password="testpass123")

    response = client.get(url)
    assert response.status_code == 200

    response = client.post(url, questionnaire_post(student_invite_view_setup))
    assert response.status_code == 302

    student_invite_view_setup["student1"].refresh_from_db()
    assert student_invite_view_setup["student1"].user == user


@pytest.mark.django_db
def test_questionnaire_works_before_classes_exist(student_invite_view_setup):
    """A semester whose classes are not up yet is not a dead end."""
    Course.objects.filter(semester=student_invite_view_setup["semester"]).delete()
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")

    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    data = questionnaire_post(student_invite_view_setup)
    data.pop("course_preferences")
    response = client.post(url, data)
    assert response.status_code == 302
    assert not CoursePreference.objects.exists()
    assert StudentRegistration.objects.count() == 1
