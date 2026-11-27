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
        start_date=timezone.localdate(),
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
        start_date=timezone.localdate(),
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
        start_date=timezone.localdate(),
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
        start_date=timezone.localdate(),
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
        start_date=timezone.localdate(),
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
    assert meeting.reminder_sent_at is None


def _semester(slug: str, status: str, days_from_now: int) -> Semester:
    start = timezone.localdate() + timedelta(days=days_from_now)
    return Semester.objects.create(
        name=slug,
        slug=slug,
        status=status,
        start_date=start,
        end_date=start + timedelta(days=90),
    )


@pytest.mark.django_db
def test_new_semesters_start_as_internal_drafts():
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.localdate(),
        end_date=timezone.localdate() + timedelta(days=90),
    )
    assert semester.status == Semester.Status.INTERNAL_DRAFT
    assert not semester.is_public


@pytest.mark.django_db
def test_current_semester_is_the_started_one():
    _semester("sp25", Semester.Status.ENDED, -200)
    started = _semester("fa25", Semester.Status.STARTED, -10)
    _semester("sp26", Semester.Status.PUBLIC_DRAFT, 100)

    assert Semester.current() == started
    assert Semester.latest_started() == started


@pytest.mark.django_db
def test_current_semester_goes_by_status_not_dates():
    """A semester past its end date is still current until it is marked ended."""
    overdue = _semester("sp25", Semester.Status.STARTED, -200)
    _semester("fa25", Semester.Status.PUBLIC_DRAFT, 30)

    assert Semester.current() == overdue


@pytest.mark.django_db
def test_current_semester_between_semesters_is_the_next_one():
    _semester("sp26", Semester.Status.ENDED, -200)
    upcoming = _semester("fa26", Semester.Status.PUBLIC_DRAFT, 30)
    _semester("sp27", Semester.Status.INTERNAL_DRAFT, 200)

    assert Semester.current() == upcoming


@pytest.mark.django_db
def test_latest_started_looks_backwards_between_semesters():
    """Its counterpart stays with what has happened, for pages that report on
    it: the standings just earned, not the empty slate ahead."""
    _semester("fa25", Semester.Status.ENDED, -400)
    finished = _semester("sp26", Semester.Status.ENDED, -200)
    _semester("fa26", Semester.Status.PUBLIC_FINALIZED, 30)

    assert Semester.latest_started() == finished


@pytest.mark.django_db
def test_current_semester_is_none_when_everything_has_ended():
    _semester("sp25", Semester.Status.ENDED, -200)

    assert Semester.current() is None


@pytest.mark.django_db
def test_only_one_semester_may_be_started():
    _semester("fa25", Semester.Status.STARTED, -10)
    second = Semester(
        name="Spring 2026",
        slug="sp26",
        status=Semester.Status.STARTED,
        start_date=timezone.localdate() + timedelta(days=100),
        end_date=timezone.localdate() + timedelta(days=200),
    )

    with pytest.raises(ValidationError, match="already started"):
        second.full_clean()


@pytest.mark.django_db
def test_a_semester_may_not_end_before_it_starts():
    backwards = Semester(
        name="Backwards",
        slug="back",
        start_date=(timezone.now() + timedelta(days=10)).date(),
        end_date=(timezone.now() - timedelta(days=10)).date(),
    )

    with pytest.raises(ValidationError, match="cannot end before it starts"):
        backwards.full_clean()


@pytest.mark.django_db
def test_editing_a_semester_does_not_clash_with_itself():
    """The overlap check has to skip the row being saved."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=10)).date(),
        end_date=(timezone.now() + timedelta(days=80)).date(),
    )

    semester.name = "Fall 2025 (renamed)"
    semester.full_clean()
