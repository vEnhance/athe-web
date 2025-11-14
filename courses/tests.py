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
    assert "Past Meeting" in response.content.decode()


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


# ============================================================================
# Join/Drop Club Tests
# ============================================================================


@pytest.mark.django_db
def test_join_club_active_semester():
    """Test that a student can join a club in an active semester."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create an active semester (current date is within the semester)
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create a club
    club = Course.objects.create(
        name="Chess Club",
        description="Learn to play chess",
        semester=active_semester,
        is_club=True,
    )

    # Create student record so they have access to the semester
    Student.objects.create(user=user, semester=active_semester)

    client.login(username="student", password="password")
    url = reverse("courses:join_club", kwargs={"pk": club.pk})
    response = client.get(url)

    # Should redirect to my_clubs
    assert response.status_code == 302
    assert response.url == reverse("courses:my_clubs")

    # Verify student is enrolled
    student = Student.objects.get(user=user, semester=active_semester)
    assert club in student.enrolled_courses.all()


@pytest.mark.django_db
def test_join_club_creates_student_record():
    """Test that joining a club creates a Student record if it doesn't exist."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create an active semester
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create a club
    club = Course.objects.create(
        name="Math Club",
        description="Math enthusiasts",
        semester=active_semester,
        is_club=True,
    )

    # No student record exists yet
    assert not Student.objects.filter(user=user, semester=active_semester).exists()

    client.login(username="student", password="password")
    url = reverse("courses:join_club", kwargs={"pk": club.pk})
    response = client.get(url)

    # Should redirect successfully
    assert response.status_code == 302

    # Verify student record was created and enrolled in club
    assert Student.objects.filter(user=user, semester=active_semester).exists()
    student = Student.objects.get(user=user, semester=active_semester)
    assert club in student.enrolled_courses.all()


@pytest.mark.django_db
def test_join_club_inactive_semester():
    """Test that a student cannot join a club in an inactive semester."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create a past semester (ended 30 days ago)
    past_semester = Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
    )

    # Create a club in the past semester
    club = Course.objects.create(
        name="Old Club",
        description="A club from the past",
        semester=past_semester,
        is_club=True,
    )

    client.login(username="student", password="password")
    url = reverse("courses:join_club", kwargs={"pk": club.pk})
    response = client.get(url, follow=True)

    # Should redirect with error message
    assert response.status_code == 200
    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "not currently active" in str(messages[0])

    # Verify student is not enrolled
    assert not Student.objects.filter(
        user=user, semester=past_semester, enrolled_courses=club
    ).exists()


@pytest.mark.django_db
def test_join_club_future_semester():
    """Test that a student cannot join a club in a future semester."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create a future semester (starts 30 days from now)
    future_semester = Semester.objects.create(
        name="Future Semester",
        slug="future",
        start_date=(timezone.now() + timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=120)).date(),
    )

    # Create a club in the future semester
    club = Course.objects.create(
        name="Future Club",
        description="A club from the future",
        semester=future_semester,
        is_club=True,
    )

    client.login(username="student", password="password")
    url = reverse("courses:join_club", kwargs={"pk": club.pk})
    response = client.get(url, follow=True)

    # Should redirect with error message
    assert response.status_code == 200
    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "not currently active" in str(messages[0])

    # Verify student is not enrolled
    assert not Student.objects.filter(
        user=user, semester=future_semester, enrolled_courses=club
    ).exists()


@pytest.mark.django_db
def test_join_club_already_enrolled():
    """Test that joining a club the student is already in is idempotent."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create an active semester
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create a club and enroll student
    club = Course.objects.create(
        name="Drama Club",
        description="Drama enthusiasts",
        semester=active_semester,
        is_club=True,
    )
    student = Student.objects.create(user=user, semester=active_semester)
    student.enrolled_courses.add(club)

    client.login(username="student", password="password")
    url = reverse("courses:join_club", kwargs={"pk": club.pk})
    response = client.get(url, follow=True)

    # Should succeed without errors
    assert response.status_code == 200
    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "already enrolled" in str(messages[0]).lower()

    # Verify student is still enrolled (and only once)
    student.refresh_from_db()
    assert student.enrolled_courses.count() == 1
    assert club in student.enrolled_courses.all()


@pytest.mark.django_db
def test_join_regular_course_fails():
    """Test that the join_club view only works for clubs, not regular courses."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create an active semester
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create a regular course (not a club)
    course = Course.objects.create(
        name="Math 101",
        description="Intro to Math",
        semester=active_semester,
        is_club=False,
    )

    client.login(username="student", password="password")
    url = reverse("courses:join_club", kwargs={"pk": course.pk})
    response = client.get(url)

    # Should return 404 since is_club=True is required
    assert response.status_code == 404


@pytest.mark.django_db
def test_drop_club_active_semester():
    """Test that a student can drop a club in an active semester."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create an active semester
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create a club and enroll student
    club = Course.objects.create(
        name="Book Club",
        description="Reading books",
        semester=active_semester,
        is_club=True,
    )
    student = Student.objects.create(user=user, semester=active_semester)
    student.enrolled_courses.add(club)

    client.login(username="student", password="password")
    url = reverse("courses:drop_club", kwargs={"pk": club.pk})
    response = client.get(url)

    # Should redirect to my_clubs
    assert response.status_code == 302
    assert response.url == reverse("courses:my_clubs")

    # Verify student is no longer enrolled
    student.refresh_from_db()
    assert club not in student.enrolled_courses.all()


@pytest.mark.django_db
def test_drop_club_inactive_semester():
    """Test that a student cannot drop a club in an inactive semester."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create a past semester
    past_semester = Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
    )

    # Create a club and enroll student
    club = Course.objects.create(
        name="Old Book Club",
        description="Old reading club",
        semester=past_semester,
        is_club=True,
    )
    student = Student.objects.create(user=user, semester=past_semester)
    student.enrolled_courses.add(club)

    client.login(username="student", password="password")
    url = reverse("courses:drop_club", kwargs={"pk": club.pk})
    response = client.get(url, follow=True)

    # Should redirect with error message
    assert response.status_code == 200
    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "not currently active" in str(messages[0])

    # Verify student is still enrolled (cannot drop from past semester)
    student.refresh_from_db()
    assert club in student.enrolled_courses.all()


@pytest.mark.django_db
def test_drop_club_not_enrolled():
    """Test that dropping a club the student isn't in handles gracefully."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create an active semester
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create a club but don't enroll student
    club = Course.objects.create(
        name="Art Club",
        description="Art enthusiasts",
        semester=active_semester,
        is_club=True,
    )
    Student.objects.create(user=user, semester=active_semester)

    client.login(username="student", password="password")
    url = reverse("courses:drop_club", kwargs={"pk": club.pk})
    response = client.get(url, follow=True)

    # Should redirect with error message
    assert response.status_code == 200
    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "not enrolled" in str(messages[0]).lower()


@pytest.mark.django_db
def test_drop_regular_course_fails():
    """Test that the drop_club view only works for clubs, not regular courses."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create an active semester
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create a regular course (not a club)
    course = Course.objects.create(
        name="Physics 101",
        description="Intro to Physics",
        semester=active_semester,
        is_club=False,
    )

    client.login(username="student", password="password")
    url = reverse("courses:drop_club", kwargs={"pk": course.pk})
    response = client.get(url)

    # Should return 404 since is_club=True is required
    assert response.status_code == 404


@pytest.mark.django_db
def test_join_club_requires_login():
    """Test that joining a club requires authentication."""
    client = Client()

    # Create an active semester and club
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )
    club = Course.objects.create(
        name="Music Club",
        description="Music lovers",
        semester=active_semester,
        is_club=True,
    )

    # Try to join without logging in
    url = reverse("courses:join_club", kwargs={"pk": club.pk})
    response = client.get(url)

    # Should redirect to login page
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_drop_club_requires_login():
    """Test that dropping a club requires authentication."""
    client = Client()

    # Create an active semester and club
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )
    club = Course.objects.create(
        name="Science Club",
        description="Science enthusiasts",
        semester=active_semester,
        is_club=True,
    )

    # Try to drop without logging in
    url = reverse("courses:drop_club", kwargs={"pk": club.pk})
    response = client.get(url)

    # Should redirect to login page
    assert response.status_code == 302
    assert "/login/" in response.url
