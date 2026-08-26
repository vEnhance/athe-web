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


def step_url(setup, step, invite="valid_invite"):
    return reverse(
        "reg:student-step",
        kwargs={"invite_id": setup[invite].id, "step": step},
    )


def you_post(setup, **overrides):
    data = {
        "student": setup["student1"].id,
        "email": "alice@example.com",
        "parent_email": "parent@example.com",
        "discord_username": "alice",
        "taken_class_before": "no",
    }
    return {**data, **overrides}


def classes_post(setup, **overrides):
    data = {
        "subject_interest_algebra": "very",
        "subject_interest_combinatorics": "somewhat",
        "subject_interest_geometry": "not",
        "subject_interest_number_theory": "very",
        "difficulty_levels": ["aime", "olympiad"],
        "first_choice": setup["geometry"].pk,
        "second_choice": setup["algebra"].pk,
        "third_choice": "",
        "avoid_courses": [],
        "course_comments": "Geometry please!",
    }
    return {**data, **overrides}


def availability_post(setup, **overrides):
    data = {
        "availability": ["sat-0900", "sat-0930", "sun-1400"],
        "availability_comments": "Busy on Sunday mornings.",
    }
    return {**data, **overrides}


def sorting_post(setup, **overrides):
    data = {
        "quiz_challenge": "plan",
        "quiz_values": "clarity",
        "quiz_compass": "logic",
        "quiz_day_off": "productive",
        "quiz_friend": "trustworthy",
        "house_request": "Owls, like last semester",
    }
    return {**data, **overrides}


def register_fully(client, setup):
    """Walk a logged-in client through all four pages."""
    for step, data in (
        ("you", you_post(setup)),
        ("classes", classes_post(setup)),
        ("availability", availability_post(setup)),
        ("sorting", sorting_post(setup)),
    ):
        response = client.post(step_url(setup, step), data)
        assert response.status_code == 302, (step, response.context["form"].errors)
    return response


@pytest.fixture
def logged_in_client():
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")
    return client


@pytest.mark.django_db
def test_invite_sends_a_logged_in_student_to_the_first_page(
    student_invite_view_setup, logged_in_client
):
    """The invite link itself is a signpost, not a page of its own."""
    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = logged_in_client.get(url)
    assert response.status_code == 302
    assert response.url == step_url(student_invite_view_setup, "you")


@pytest.mark.django_db
def test_first_page_lists_the_roster_in_a_select(
    student_invite_view_setup, logged_in_client
):
    response = logged_in_client.get(step_url(student_invite_view_setup, "you"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Alice Johnson" in content
    assert "Bob Smith" in content
    # A hundred radio buttons is a hundred lines to scroll; it is a dropdown.
    assert "data-tom-select" in content
    assert "<select" in content


@pytest.mark.django_db
def test_later_pages_are_locked_until_the_earlier_ones_are_done(
    student_invite_view_setup, logged_in_client
):
    """Pages 2-4 need a registration row to write to, so page 1 comes first."""
    for step in ("classes", "availability", "sorting"):
        response = logged_in_client.get(step_url(student_invite_view_setup, step))
        assert response.status_code == 302
        assert response.url == step_url(student_invite_view_setup, "you")

    logged_in_client.post(
        step_url(student_invite_view_setup, "you"),
        you_post(student_invite_view_setup),
    )
    assert (
        logged_in_client.get(step_url(student_invite_view_setup, "classes")).status_code
        == 200
    )
    # Jumping to the end lands on the first page still to be filled in.
    response = logged_in_client.get(step_url(student_invite_view_setup, "sorting"))
    assert response.url == step_url(student_invite_view_setup, "classes")


@pytest.mark.django_db
def test_unknown_step_is_a_404(student_invite_view_setup, logged_in_client):
    assert (
        logged_in_client.get(
            step_url(student_invite_view_setup, "nonsense")
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_first_page_binds_the_user_and_moves_on(
    student_invite_view_setup, logged_in_client
):
    response = logged_in_client.post(
        step_url(student_invite_view_setup, "you"),
        you_post(student_invite_view_setup),
    )
    assert response.status_code == 302
    assert response.url == step_url(student_invite_view_setup, "classes")

    student = student_invite_view_setup["student1"]
    student.refresh_from_db()
    assert student.user is not None
    registration = StudentRegistration.objects.get(student=student)
    assert registration.email == "alice@example.com"
    assert registration.parent_email == "parent@example.com"
    assert registration.discord_username == "alice"
    assert registration.taken_class_before is False
    assert registration.completed_steps == ["you"]


@pytest.mark.django_db
def test_walking_all_four_pages_saves_everything(
    student_invite_view_setup, logged_in_client
):
    response = register_fully(logged_in_client, student_invite_view_setup)
    assert response.url == reverse("home:index")

    registration = StudentRegistration.objects.get(
        student=student_invite_view_setup["student1"]
    )
    assert registration.completed_steps == ["you", "classes", "availability", "sorting"]
    assert registration.subject_interest == {
        "algebra": "very",
        "combinatorics": "somewhat",
        "geometry": "not",
        "number_theory": "very",
    }
    assert registration.difficulty_levels == ["aime", "olympiad"]
    assert registration.availability == ["sat-0900", "sat-0930", "sun-1400"]
    assert registration.quiz_challenge == "plan"
    assert registration.house_request == "Owls, like last semester"

    # Only the top picks are stored; the rest of the catalogue is left alone.
    assert [
        (pref.course.name, pref.rank, pref.excluded)
        for pref in CoursePreference.objects.filter(registration=registration)
    ] == [("Geometry", 1, False), ("Algebra", 2, False)]


@pytest.mark.django_db
def test_classes_page_stores_the_avoid_pile(
    student_invite_view_setup, logged_in_client
):
    logged_in_client.post(
        step_url(student_invite_view_setup, "you"), you_post(student_invite_view_setup)
    )
    response = logged_in_client.post(
        step_url(student_invite_view_setup, "classes"),
        classes_post(
            student_invite_view_setup,
            second_choice="",
            avoid_courses=[student_invite_view_setup["algebra"].pk],
        ),
    )
    assert response.status_code == 302

    registration = StudentRegistration.objects.get(
        student=student_invite_view_setup["student1"]
    )
    assert {
        pref.course.name: (pref.rank, pref.excluded)
        for pref in CoursePreference.objects.filter(registration=registration)
    } == {"Geometry": (1, False), "Algebra": (None, True)}


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"second_choice": "$geometry"}, "different class for each choice"),
        ({"first_choice": "", "second_choice": "$algebra"}, "in order"),
        ({"avoid_courses": ["$geometry"]}, "rather not take"),
        ({"subject_interest_geometry": ""}, "how interested you are in Geometry"),
    ],
)
@pytest.mark.django_db
def test_classes_page_rejects_contradictions(
    student_invite_view_setup, logged_in_client, overrides, message
):
    logged_in_client.post(
        step_url(student_invite_view_setup, "you"), you_post(student_invite_view_setup)
    )
    resolved = {
        key: (
            student_invite_view_setup[value[1:]].pk
            if isinstance(value, str) and value.startswith("$")
            else [student_invite_view_setup[item[1:]].pk for item in value]
            if isinstance(value, list)
            else value
        )
        for key, value in overrides.items()
    }
    response = logged_in_client.post(
        step_url(student_invite_view_setup, "classes"),
        classes_post(student_invite_view_setup, **resolved),
    )
    assert response.status_code == 200
    assert message in str(response.context["form"].errors)
    assert not CoursePreference.objects.exists()


@pytest.mark.django_db
def test_classes_page_requires_a_difficulty_band(
    student_invite_view_setup, logged_in_client
):
    logged_in_client.post(
        step_url(student_invite_view_setup, "you"), you_post(student_invite_view_setup)
    )
    response = logged_in_client.post(
        step_url(student_invite_view_setup, "classes"),
        classes_post(student_invite_view_setup, difficulty_levels=[]),
    )
    assert response.status_code == 200
    assert response.context["form"].errors["difficulty_levels"]


@pytest.mark.django_db
def test_availability_page_requires_some_availability(
    student_invite_view_setup, logged_in_client
):
    """Nothing can be scheduled for a student who marks no time at all."""
    logged_in_client.post(
        step_url(student_invite_view_setup, "you"), you_post(student_invite_view_setup)
    )
    logged_in_client.post(
        step_url(student_invite_view_setup, "classes"),
        classes_post(student_invite_view_setup),
    )
    for availability in ([], ["mon-0300"]):
        response = logged_in_client.post(
            step_url(student_invite_view_setup, "availability"),
            availability_post(student_invite_view_setup, availability=availability),
        )
        assert response.status_code == 200
        assert response.context["form"].errors["availability"]


@pytest.mark.django_db
def test_first_page_rejects_a_claimed_name(student_invite_view_setup, logged_in_client):
    """Picking a name someone else claimed is refused, form intact."""
    response = logged_in_client.post(
        step_url(student_invite_view_setup, "you"),
        you_post(
            student_invite_view_setup, student=student_invite_view_setup["student2"].id
        ),
    )
    assert response.status_code == 200
    assert "already been claimed" in str(response.context["form"].errors["student"])
    assert not StudentRegistration.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("bad", ["not-a-number", "999999", ""])
def test_first_page_rejects_a_bad_student_id(
    student_invite_view_setup, logged_in_client, bad
):
    response = logged_in_client.post(
        step_url(student_invite_view_setup, "you"),
        you_post(student_invite_view_setup, student=bad),
    )
    assert response.status_code == 200
    assert response.context["form"].errors["student"]


@pytest.mark.django_db
def test_first_page_rejects_a_student_from_another_semester(
    student_invite_view_setup, logged_in_client
):
    outsider = Student.objects.create(
        airtable_name="Carol Elsewhere",
        semester=student_invite_view_setup["ended_semester"],
    )
    response = logged_in_client.post(
        step_url(student_invite_view_setup, "you"),
        you_post(student_invite_view_setup, student=outsider.pk),
    )
    assert response.status_code == 200
    assert response.context["form"].errors["student"]
    outsider.refresh_from_db()
    assert outsider.user is None


@pytest.mark.django_db
def test_a_registered_student_can_come_back_and_edit(student_invite_view_setup):
    """Every page stays open once done, and saving one returns them home."""
    client = Client()
    client.login(username="bobsmith", password="testpass123")
    setup = student_invite_view_setup
    register_fully(client, {**setup, "student1": setup["student2"]})

    # The name is settled, so page 1 no longer offers the roster.
    response = client.get(step_url(setup, "you"))
    assert response.status_code == 200
    assert "Alice Johnson" not in response.content.decode()
    assert response.context["complete"] is True

    response = client.post(
        step_url(setup, "availability"),
        availability_post(setup, availability=["sun-2000"]),
    )
    assert response.status_code == 302
    assert response.url == reverse("home:index")

    registration = StudentRegistration.objects.get(student=setup["student2"])
    assert registration.availability == ["sun-2000"]

    # Re-saving the classes page replaces the picks instead of adding to them.
    client.post(
        step_url(setup, "classes"),
        classes_post(setup, first_choice=setup["algebra"].pk, second_choice=""),
    )
    assert [
        (pref.course.name, pref.rank)
        for pref in CoursePreference.objects.filter(registration=registration)
    ] == [("Algebra", 1)]
    assert StudentRegistration.objects.count() == 1


@pytest.mark.django_db
def test_no_students_available(student_invite_view_setup, logged_in_client):
    """An empty roster says so rather than showing an empty questionnaire."""
    Student.objects.filter(semester=student_invite_view_setup["semester"]).delete()
    url = reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )
    response = logged_in_client.get(url)
    assert response.status_code == 200
    assert "no students" in response.content.decode().lower()


@pytest.mark.django_db
def test_steps_require_login(student_invite_view_setup):
    """An anonymous visitor is sent to the front door to log in."""
    response = Client().get(step_url(student_invite_view_setup, "you"))
    assert response.status_code == 302
    assert response.url == reverse(
        "reg:add-student",
        kwargs={"invite_id": student_invite_view_setup["valid_invite"].id},
    )


@pytest.mark.django_db
def test_expired_invite_closes_the_steps_too(student_invite_view_setup):
    client = Client()
    User.objects.create_user(username="newuser", password="testpass123")
    client.login(username="newuser", password="testpass123")
    response = client.get(step_url(student_invite_view_setup, "you", "expired_invite"))
    assert response.status_code == 200
    assert "expired" in response.content.decode()


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
    register_fully(client, student_invite_view_setup)

    student_invite_view_setup["student1"].refresh_from_db()
    assert student_invite_view_setup["student1"].user == user


@pytest.mark.django_db
def test_questionnaire_works_before_classes_exist(
    student_invite_view_setup, logged_in_client
):
    """A semester whose classes are not up yet is not a dead end."""
    Course.objects.filter(semester=student_invite_view_setup["semester"]).delete()
    logged_in_client.post(
        step_url(student_invite_view_setup, "you"), you_post(student_invite_view_setup)
    )
    response = logged_in_client.post(
        step_url(student_invite_view_setup, "classes"),
        classes_post(student_invite_view_setup, first_choice="", second_choice=""),
    )
    assert response.status_code == 302
    assert not CoursePreference.objects.exists()
    assert StudentRegistration.objects.get().difficulty_levels == ["aime", "olympiad"]
