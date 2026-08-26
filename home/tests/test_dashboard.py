from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseMeeting, Semester, Student
from housepoints.models import Award
from yearbook.models import YearbookEntry


@pytest.fixture
def semester() -> Semester:
    today = timezone.localdate()
    return Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=80),
    )


@pytest.fixture
def student(semester: Semester) -> Student:
    user = User.objects.create_user(
        username="lucy", password="password", first_name="Lucy"
    )
    return Student.objects.create(
        user=user,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Lucy",
    )


@pytest.fixture
def client_for():
    def _login(username: str) -> Client:
        client = Client()
        client.login(username=username, password="password")
        return client

    return _login


@pytest.mark.django_db
def test_root_shows_splash_when_logged_out():
    """Anonymous visitors still get the public homepage at /."""
    response = Client().get(reverse("home:index"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Bringing extraordinary young women together" in content
    assert "Welcome back" not in content


@pytest.mark.django_db
def test_root_shows_dashboard_when_logged_in(student: Student, client_for):
    """Logged-in users get the dashboard at / instead of the splash page."""
    response = client_for("lucy").get(reverse("home:index"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Welcome back, Lucy" in content
    assert "Bringing extraordinary young women together" not in content


@pytest.mark.django_db
def test_dashboard_lists_classes_and_clubs_with_next_meeting(
    semester: Semester, student: Student, client_for
):
    """Enrolled classes and clubs are listed apart, each with its next meeting."""
    klass = Course.objects.create(
        name="Intro to Olympiad", description="", semester=semester
    )
    club = Course.objects.create(
        name="Origami Club", description="", semester=semester, is_club=True
    )
    klass.students.add(student)
    club.students.add(student)

    now = timezone.now()
    CourseMeeting.objects.create(
        course=klass, start_time=now - timedelta(days=7), title="Old lesson"
    )
    CourseMeeting.objects.create(
        course=klass, start_time=now + timedelta(days=1), title="Next lesson"
    )
    CourseMeeting.objects.create(
        course=klass, start_time=now + timedelta(days=8), title="Later lesson"
    )

    content = client_for("lucy").get(reverse("home:index")).content.decode()

    assert "Intro to Olympiad" in content
    assert "Origami Club" in content
    # Only the soonest upcoming meeting is shown for the class.
    assert "Next lesson" in content
    assert "Old lesson" not in content
    assert "Later lesson" not in content
    # The club has no meetings scheduled at all.
    assert "No meetings scheduled" in content


@pytest.mark.django_db
def test_dashboard_omits_courses_from_inactive_semesters(
    semester: Semester, student: Student, client_for
):
    """Courses from a semester that has ended stay off the dashboard."""
    old_semester = Semester.objects.create(
        name="Spring 2025",
        slug="sp25",
        start_date=timezone.localdate() - timedelta(days=200),
        end_date=timezone.localdate() - timedelta(days=100),
    )
    old_student = Student.objects.create(
        user=student.user, semester=old_semester, airtable_name="Lucy"
    )
    old_course = Course.objects.create(
        name="Ancient History of Numbers", description="", semester=old_semester
    )
    old_course.students.add(old_student)

    content = client_for("lucy").get(reverse("home:index")).content.decode()

    assert "Ancient History of Numbers" not in content


@pytest.mark.django_db
def test_dashboard_house_squares(semester: Semester, student: Student, client_for):
    """The house squares show the house total and the student's own total."""
    housemate = Student.objects.create(
        semester=semester, house=Student.House.OWL, airtable_name="Housemate"
    )
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=housemate,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )

    content = client_for("lucy").get(reverse("home:index")).content.decode()

    assert "Owls" in content
    assert "10 house points" in content
    assert reverse("housepoints:my_awards") in content


@pytest.mark.django_db
def test_dashboard_prompts_for_missing_yearbook_entry(
    semester: Semester, student: Student, client_for
):
    """Without an entry, the yearbook square names the semester and invites one."""
    content = client_for("lucy").get(reverse("home:index")).content.decode()

    assert "Fall 2025 yearbook" in content
    assert "Write my entry" in content
    assert reverse("yearbook:create", kwargs={"student_pk": student.pk}) in content


@pytest.mark.django_db
def test_dashboard_previews_existing_yearbook_entry(
    semester: Semester, student: Student, client_for
):
    """With an entry, the square previews it and links to the edit form."""
    entry = YearbookEntry.objects.create(
        student=student, display_name="Lucy L.", bio="I like combinatorics."
    )

    content = client_for("lucy").get(reverse("home:index")).content.decode()

    assert "Lucy L." in content
    assert "I like combinatorics." in content
    assert reverse("yearbook:edit", kwargs={"pk": entry.pk}) in content
    assert reverse("yearbook:entry_list", kwargs={"slug": semester.slug}) in content


@pytest.mark.django_db
def test_dashboard_staff_section_is_staff_only(client_for):
    """Staff tools only render for staff, and admin tools only for superusers."""
    User.objects.create_user(username="pupil", password="password")
    User.objects.create_user(username="teacher", password="password", is_staff=True)
    User.objects.create_user(
        username="boss", password="password", is_staff=True, is_superuser=True
    )

    pupil = client_for("pupil").get(reverse("home:index")).content.decode()
    assert "TA Sign-in Sheet" not in pupil
    assert "Bulk Create Students" not in pupil

    teacher = client_for("teacher").get(reverse("home:index")).content.decode()
    assert "TA Sign-in Sheet" in teacher
    assert reverse("courses:staff_schedule") in teacher
    assert "Bulk Create Students" not in teacher

    boss = client_for("boss").get(reverse("home:index")).content.decode()
    assert "TA Sign-in Sheet" in boss
    assert "Bulk Create Students" in boss
    assert reverse("reg:upload-assignments") in boss
    assert reverse("admin:index") in boss


@pytest.mark.django_db
def test_dashboard_works_for_staff_without_student_record(client_for):
    """Staff have no Student row, so they get the generic house/yearbook squares."""
    User.objects.create_user(username="teacher", password="password", is_staff=True)

    response = client_for("teacher").get(reverse("home:index"))
    content = response.content.decode()

    assert response.status_code == 200
    assert reverse("housepoints:leaderboard") in content
    assert reverse("yearbook:index") in content
    assert "Write my entry" not in content
    assert "Edit my entry" not in content


@pytest.mark.django_db
def test_navbar_dropdown_is_trimmed(student: Student, client_for):
    """The user dropdown keeps the dashboard, blog and account entries only."""
    content = client_for("lucy").get(reverse("home:index")).content.decode()

    assert '<a class="dropdown-item" href="/">Dashboard</a>' in content
    assert "My Blog Posts" in content
    assert "Profile Settings" in content
    assert "Login Providers" in content
    # Moved onto the dashboard itself.
    assert "House Standings" not in content
    assert "Clubs and Events" not in content
