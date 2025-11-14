from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.management.commands.send_discord_reminders import Command
from courses.models import Course, CourseMeeting, Semester, Student


@pytest.mark.django_db
def test_course_creation():
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now(),
        end_date=timezone.now(),
    )
    course = Course.objects.create(
        name="Intro to Django",
        description="Learn the basics of Django web development.",
        semester=fall,
    )

    assert course.name == "Intro to Django"
    assert course.semester.slug == "fa25"


@pytest.mark.django_db
def test_course_with_links():
    """Test that a course can have all the new URL fields."""
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Advanced Python",
        description="Advanced Python programming",
        semester=fall,
        regular_meeting_time="5pm-6pm ET on Saturday",
        google_classroom_direct_link="https://classroom.google.com/c/12345",
        google_classroom_join_link="https://classroom.google.com/join/12345",
        zoom_meeting_link="https://zoom.us/j/12345",
        discord_webhook="https://discord.com/api/webhooks/12345/abcde",
        discord_role_id="123456789",
    )

    assert course.regular_meeting_time == "5pm-6pm ET on Saturday"
    assert "classroom.google.com" in course.google_classroom_direct_link
    assert "zoom.us" in course.zoom_meeting_link
    assert "discord.com" in course.discord_webhook
    assert course.discord_role_id == "123456789"


@pytest.mark.django_db
def test_student_creation():
    """Test student model with unique constraint."""
    user = User.objects.create_user(username="testuser", password="password")
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(user=user, semester=fall)

    assert student.user == user
    assert student.semester == fall
    assert str(student) == f"testuser ({fall})"


@pytest.mark.django_db
def test_student_enrollment():
    """Test that students can enroll in courses."""
    user = User.objects.create_user(username="testuser", password="password")
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course1 = Course.objects.create(
        name="Math 101", description="Basic math", semester=fall
    )
    course2 = Course.objects.create(
        name="CS 101", description="Intro to CS", semester=fall
    )
    student = Student.objects.create(user=user, semester=fall)
    student.enrolled_courses.add(course1, course2)

    assert student.enrolled_courses.count() == 2
    assert course1 in student.enrolled_courses.all()
    assert course2 in student.enrolled_courses.all()


@pytest.mark.django_db
def test_student_enrollment_semester_validation():
    """Test that students cannot enroll in courses from different semesters."""
    user = User.objects.create_user(username="testuser", password="password")
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    spring = Semester.objects.create(
        name="Spring 2026",
        slug="sp26",
        start_date=(timezone.now() + timedelta(days=120)).date(),
        end_date=(timezone.now() + timedelta(days=210)).date(),
    )
    fall_course = Course.objects.create(
        name="Fall Math", description="Math in fall", semester=fall
    )
    spring_course = Course.objects.create(
        name="Spring Math", description="Math in spring", semester=spring
    )

    # Create student for fall semester
    student = Student.objects.create(user=user, semester=fall)
    student.enrolled_courses.add(fall_course)

    # Try to enroll in a spring course - this should fail validation
    student.enrolled_courses.add(spring_course)

    with pytest.raises(ValidationError) as exc_info:
        student.clean()

    assert "Spring Math" in str(exc_info.value)
    assert str(fall) in str(exc_info.value)


@pytest.mark.django_db
def test_course_meeting_creation():
    """Test creating a course meeting."""
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Algebra", description="Algebra course", semester=fall
    )
    start_time = timezone.now() + timedelta(hours=2)
    meeting = CourseMeeting.objects.create(
        course=course, start_time=start_time, title="Introduction to Algebra"
    )

    assert meeting.course == course
    assert meeting.title == "Introduction to Algebra"
    assert meeting.reminder_sent is False


@pytest.mark.django_db
def test_course_detail_view_staff_access():
    """Test that staff can access course detail view."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course", description="Test", semester=fall
    )

    client.login(username="staff", password="password")
    url = reverse("courses:course_detail", kwargs={"pk": course.pk})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_course_detail_view_enrolled_student_access():
    """Test that enrolled students can access course detail view."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course", description="Test", semester=fall
    )
    student = Student.objects.create(user=user, semester=fall)
    student.enrolled_courses.add(course)

    client.login(username="student", password="password")
    url = reverse("courses:course_detail", kwargs={"pk": course.pk})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_course_detail_view_unenrolled_student_denied():
    """Test that unenrolled students cannot access course detail view."""
    client = Client()
    User.objects.create_user(username="student", password="password")
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course", description="Test", semester=fall
    )

    client.login(username="student", password="password")
    url = reverse("courses:course_detail", kwargs={"pk": course.pk})
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_course_detail_view_shows_upcoming_meetings():
    """Test that course detail view shows upcoming meetings."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course", description="Test", semester=fall
    )
    # Create past and future meetings
    CourseMeeting.objects.create(
        course=course,
        start_time=timezone.now() - timedelta(hours=1),
        title="Past Meeting",
    )
    CourseMeeting.objects.create(
        course=course,
        start_time=timezone.now() + timedelta(hours=1),
        title="Future Meeting",
    )

    client.login(username="staff", password="password")
    url = reverse("courses:course_detail", kwargs={"pk": course.pk})
    response = client.get(url)

    assert response.status_code == 200
    assert "Future Meeting" in response.content.decode()
    assert "Past Meeting" not in response.content.decode()


@pytest.mark.django_db
@patch("requests.post")
def test_discord_reminder_command(mock_post):
    """Test the Discord reminder management command."""
    # Mock successful Discord API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=fall,
        discord_webhook="https://discord.com/api/webhooks/test",
        discord_role_id="123456",
        zoom_meeting_link="https://zoom.us/j/test",
    )
    # Create a meeting within 24 hours
    meeting = CourseMeeting.objects.create(
        course=course,
        start_time=timezone.now() + timedelta(hours=12),
        title="Test Meeting",
    )

    # Run the command
    command = Command()
    out = StringIO()
    command.stdout = out
    command.handle()

    # Check that Discord API was called
    assert mock_post.called
    call_args = mock_post.call_args
    assert course.discord_webhook in call_args[0]
    assert "Test Meeting" in call_args[1]["json"]["content"]

    # Check that meeting was marked as sent
    meeting.refresh_from_db()
    assert meeting.reminder_sent is True


@pytest.mark.django_db
def test_discord_reminder_command_no_webhook():
    """Test that command skips meetings without webhook."""
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course", description="Test", semester=fall
    )
    meeting = CourseMeeting.objects.create(
        course=course,
        start_time=timezone.now() + timedelta(hours=12),
        title="Test Meeting",
    )

    command = Command()
    out = StringIO()
    command.stdout = out
    command.handle()

    # Meeting should not be marked as sent
    meeting.refresh_from_db()
    assert meeting.reminder_sent is False
