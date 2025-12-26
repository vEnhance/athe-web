from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

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
    user = User.objects.create_user(
        first_name="Test", last_name="User", username="testuser", password="password"
    )
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(user=user, semester=fall)

    assert student.user == user
    assert student.semester == fall
    assert str(student) == "Test User"


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
    course1.students.add(student)
    course2.students.add(student)

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
    fall_course.students.add(student)

    # Try to enroll in a spring course - this should fail validation
    spring_course.students.add(student)

    # Now validation is on the course - spring_course should fail because
    # it has a student from a different semester
    with pytest.raises(ValidationError) as exc_info:
        spring_course.clean()

    assert str(student) in str(exc_info.value)
    assert str(spring) in str(exc_info.value)


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
def test_semester_visible_by_default():
    """Test that new semesters are visible by default."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    assert semester.visible is True


@pytest.mark.django_db
def test_get_current_semester():
    """Test that get_current_semester returns the active semester."""
    # Create a current semester
    current = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=10)).date(),
        end_date=(timezone.now() + timedelta(days=80)).date(),
    )
    # Create a past semester
    Semester.objects.create(
        name="Spring 2025",
        slug="sp25",
        start_date=(timezone.now() - timedelta(days=200)).date(),
        end_date=(timezone.now() - timedelta(days=100)).date(),
    )
    # Create a future semester
    Semester.objects.create(
        name="Spring 2026",
        slug="sp26",
        start_date=(timezone.now() + timedelta(days=100)).date(),
        end_date=(timezone.now() + timedelta(days=200)).date(),
    )

    result = Semester.get_current_semester()
    assert result == current


@pytest.mark.django_db
def test_get_current_semester_no_active():
    """Test that get_current_semester raises ValueError when no active semester."""
    # Create only past semesters
    Semester.objects.create(
        name="Spring 2025",
        slug="sp25",
        start_date=(timezone.now() - timedelta(days=200)).date(),
        end_date=(timezone.now() - timedelta(days=100)).date(),
    )

    with pytest.raises(ValueError, match="No active semester found"):
        Semester.get_current_semester()


@pytest.mark.django_db
def test_get_current_semester_multiple_overlapping():
    """Test that get_current_semester raises ValueError with overlapping semesters."""
    # Create two overlapping semesters
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=10)).date(),
        end_date=(timezone.now() + timedelta(days=80)).date(),
    )
    Semester.objects.create(
        name="Winter 2025",
        slug="wi25",
        start_date=(timezone.now() - timedelta(days=5)).date(),
        end_date=(timezone.now() + timedelta(days=85)).date(),
    )

    with pytest.raises(ValueError, match="Multiple active semesters found"):
        Semester.get_current_semester()
