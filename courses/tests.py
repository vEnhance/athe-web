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
from home.models import StaffPhotoListing


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
    course.students.add(student)

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
        discord_reminders_enabled=True,
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
    assert (
        not Student.objects.filter(user=user, semester=past_semester)
        .filter(enrolled_courses=club)
        .exists()
    )


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
    assert (
        not Student.objects.filter(user=user, semester=future_semester)
        .filter(enrolled_courses=club)
        .exists()
    )


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
    club.students.add(student)

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
    club.students.add(student)

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
    club.students.add(student)

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


# ============================================================================
# Query Optimization Tests for my_courses and my_clubs
# ============================================================================


@pytest.mark.django_db
def test_my_courses_query_count():
    """Test that my_courses uses O(1) queries regardless of data size."""
    from django.test.utils import CaptureQueriesContext
    from django.db import connection

    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create multiple semesters
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=60)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )
    spring = Semester.objects.create(
        name="Spring 2026",
        slug="sp26",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )

    # Create multiple courses
    course1 = Course.objects.create(
        name="Math 101", description="Basic math", semester=fall, is_club=False
    )
    course2 = Course.objects.create(
        name="CS 101", description="Intro to CS", semester=fall, is_club=False
    )
    course3 = Course.objects.create(
        name="Physics 101", description="Physics", semester=spring, is_club=False
    )
    course4 = Course.objects.create(
        name="Chemistry 101", description="Chemistry", semester=spring, is_club=False
    )

    # Create student records and enroll in multiple courses
    student1 = Student.objects.create(user=user, semester=fall)
    course1.students.add(student1)
    course2.students.add(student1)
    student2 = Student.objects.create(user=user, semester=spring)
    course3.students.add(student2)

    # User is also a leader of one course
    course4.leaders.add(user)

    client.login(username="student", password="password")

    # Count queries
    with CaptureQueriesContext(connection) as context:
        url = reverse("courses:my_courses")
        response = client.get(url)

    # Should use a constant number of queries:
    # 1. Session/auth queries (vary by Django version)
    # 2. Student records with prefetch
    # 3. Prefetch courses query
    # 4. Led courses query
    # Total should be around 5-6 queries maximum
    assert response.status_code == 200
    assert len(context.captured_queries) <= 6, (
        f"Expected ≤6 queries, got {len(context.captured_queries)}"
    )

    # Verify all courses are in the response
    content = response.content.decode()
    assert "Math 101" in content
    assert "CS 101" in content
    assert "Physics 101" in content
    assert "Chemistry 101" in content


@pytest.mark.django_db
def test_my_courses_functionality():
    """Test that my_courses correctly shows enrolled and led courses."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create semesters
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=60)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create courses and clubs
    course1 = Course.objects.create(
        name="Math 101", description="Math", semester=fall, is_club=False
    )
    course2 = Course.objects.create(
        name="CS 101", description="CS", semester=fall, is_club=False
    )
    club1 = Course.objects.create(
        name="Chess Club", description="Chess", semester=fall, is_club=True
    )

    # Enroll in courses and clubs
    student = Student.objects.create(user=user, semester=fall)
    course1.students.add(student)
    club1.students.add(student)

    # User is a leader of another course
    course2.leaders.add(user)

    client.login(username="student", password="password")
    url = reverse("courses:my_courses")
    response = client.get(url)

    content = response.content.decode()
    # Should show enrolled courses and led courses, but NOT clubs
    assert "Math 101" in content
    assert "CS 101" in content
    assert "Chess Club" not in content


@pytest.mark.django_db
def test_my_clubs_query_count():
    """Test that my_clubs uses O(1) queries regardless of data size."""
    from django.test.utils import CaptureQueriesContext
    from django.db import connection

    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create an active semester
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create multiple clubs
    club1 = Course.objects.create(
        name="Chess Club", description="Chess", semester=active_semester, is_club=True
    )
    club2 = Course.objects.create(
        name="Math Club", description="Math", semester=active_semester, is_club=True
    )
    club3 = Course.objects.create(
        name="Art Club", description="Art", semester=active_semester, is_club=True
    )
    Course.objects.create(
        name="Music Club", description="Music", semester=active_semester, is_club=True
    )

    # Create student record and enroll in some clubs
    student = Student.objects.create(user=user, semester=active_semester)
    club1.students.add(student)
    club2.students.add(student)

    # User is a leader of one club
    club3.leaders.add(user)

    client.login(username="student", password="password")

    # Count queries
    with CaptureQueriesContext(connection) as context:
        url = reverse("courses:my_clubs")
        response = client.get(url)

    # Should use a constant number of queries:
    # 1. Session/auth queries
    # 2. Active student records with prefetch
    # 3. Prefetch enrolled clubs
    # 4. Led clubs query
    # 5. All active clubs query
    # Total should be around 6-7 queries maximum
    assert response.status_code == 200
    assert len(context.captured_queries) <= 7, (
        f"Expected ≤7 queries, got {len(context.captured_queries)}"
    )

    # Verify functionality is maintained
    enrolled_clubs = response.context["enrolled_clubs"]
    available_clubs = response.context["available_clubs"]
    assert len(enrolled_clubs) == 3  # club1, club2, club3 (as leader)
    assert len(available_clubs) == 1  # Music Club


@pytest.mark.django_db
def test_my_clubs_functionality():
    """Test that my_clubs correctly splits enrolled and available clubs."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create an active semester
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create clubs
    enrolled_club = Course.objects.create(
        name="Chess Club",
        description="Chess",
        semester=active_semester,
        is_club=True,
    )
    led_club = Course.objects.create(
        name="Math Club", description="Math", semester=active_semester, is_club=True
    )
    available_club = Course.objects.create(
        name="Art Club", description="Art", semester=active_semester, is_club=True
    )

    # Create student record and enroll in one club
    student = Student.objects.create(user=user, semester=active_semester)
    enrolled_club.students.add(student)

    # User is a leader of another club
    led_club.leaders.add(user)

    client.login(username="student", password="password")
    url = reverse("courses:my_clubs")
    response = client.get(url)

    assert response.status_code == 200
    enrolled_clubs = response.context["enrolled_clubs"]
    available_clubs = response.context["available_clubs"]

    # Check enrolled clubs (should include both enrolled and led)
    enrolled_club_ids = {c.id for c in enrolled_clubs}
    assert enrolled_club.id in enrolled_club_ids
    assert led_club.id in enrolled_club_ids

    # Check available clubs
    available_club_ids = {c.id for c in available_clubs}
    assert available_club.id in available_club_ids
    assert enrolled_club.id not in available_club_ids
    assert led_club.id not in available_club_ids


@pytest.mark.django_db
def test_my_clubs_no_active_semester():
    """Test that my_clubs handles users with no active semester."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create a past semester
    past_semester = Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
    )

    # Create a club in the past semester
    Course.objects.create(
        name="Old Club", description="Old", semester=past_semester, is_club=True
    )

    client.login(username="student", password="password")
    url = reverse("courses:my_clubs")
    response = client.get(url)

    assert response.status_code == 200
    assert response.context["has_active_semester"] is False
    assert len(response.context["enrolled_clubs"]) == 0
    assert len(response.context["available_clubs"]) == 0


@pytest.mark.django_db
def test_my_courses_excludes_clubs():
    """Test that my_courses excludes clubs from the results."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=60)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )

    # Create a course and a club
    course = Course.objects.create(
        name="Math 101", description="Math", semester=semester, is_club=False
    )
    club = Course.objects.create(
        name="Chess Club", description="Chess", semester=semester, is_club=True
    )

    # Enroll in both
    student = Student.objects.create(user=user, semester=semester)
    course.students.add(student)
    club.students.add(student)

    client.login(username="student", password="password")
    url = reverse("courses:my_courses")
    response = client.get(url)

    enrolled_courses = response.context["enrolled_courses"]
    course_names = {c.name for c in enrolled_courses}

    # Should only include the course, not the club
    assert "Math 101" in course_names
    assert "Chess Club" not in course_names


# ============================================================================
# Auto-add Course Leader Tests
# ============================================================================


@pytest.mark.django_db
def test_course_auto_adds_instructor_as_leader():
    """Test that creating a course with an instructor automatically adds them as a leader."""
    # Create a user and staff listing
    user = User.objects.create_user(username="instructor1", password="password")
    staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Dr. Smith",
        slug="dr-smith",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course with the instructor
    course = Course.objects.create(
        name="Advanced Math",
        description="Advanced math course",
        semester=semester,
        instructor=staff,
    )

    # Verify the instructor's user was automatically added as a leader
    assert user in course.leaders.all()
    assert course.leaders.count() == 1


@pytest.mark.django_db
def test_course_instructor_without_user_no_error():
    """Test that a course with an instructor that has no user doesn't cause errors."""
    # Create a staff listing without a user
    staff = StaffPhotoListing.objects.create(
        user=None,
        display_name="Dr. Jones",
        slug="dr-jones",
        role="Guest Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course with the instructor (should not raise an error)
    course = Course.objects.create(
        name="Guest Lecture",
        description="Special guest lecture",
        semester=semester,
        instructor=staff,
    )

    # Verify no leaders were added
    assert course.leaders.count() == 0


@pytest.mark.django_db
def test_course_without_instructor_no_error():
    """Test that a course without an instructor doesn't cause errors."""
    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course without an instructor
    course = Course.objects.create(
        name="Self-Study Course",
        description="Self-paced learning",
        semester=semester,
        instructor=None,
    )

    # Verify no leaders were added
    assert course.leaders.count() == 0


@pytest.mark.django_db
def test_course_update_instructor_adds_leader():
    """Test that updating a course to add an instructor automatically adds them as a leader."""
    # Create a user and staff listing
    user = User.objects.create_user(username="instructor2", password="password")
    staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Dr. Brown",
        slug="dr-brown",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course without an instructor
    course = Course.objects.create(
        name="Physics 101",
        description="Basic physics",
        semester=semester,
    )

    # Verify no leaders initially
    assert course.leaders.count() == 0

    # Update the course to add an instructor
    course.instructor = staff
    course.save()

    # Verify the instructor's user was automatically added as a leader
    assert user in course.leaders.all()
    assert course.leaders.count() == 1


@pytest.mark.django_db
def test_course_instructor_idempotent():
    """Test that saving a course multiple times doesn't duplicate the leader."""
    # Create a user and staff listing
    user = User.objects.create_user(username="instructor3", password="password")
    staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Dr. Lee",
        slug="dr-lee",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course with the instructor
    course = Course.objects.create(
        name="Chemistry 101",
        description="Basic chemistry",
        semester=semester,
        instructor=staff,
    )

    # Verify the leader was added
    assert course.leaders.count() == 1
    assert user in course.leaders.all()

    # Save the course again
    course.save()

    # Verify the leader count didn't increase
    assert course.leaders.count() == 1
    assert user in course.leaders.all()


@pytest.mark.django_db
def test_course_change_instructor_adds_new_leader():
    """Test that changing the instructor adds the new instructor as a leader."""
    # Create two users and staff listings
    user1 = User.objects.create_user(username="instructor4", password="password")
    staff1 = StaffPhotoListing.objects.create(
        user=user1,
        display_name="Dr. Taylor",
        slug="dr-taylor",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )

    user2 = User.objects.create_user(username="instructor5", password="password")
    staff2 = StaffPhotoListing.objects.create(
        user=user2,
        display_name="Dr. Wilson",
        slug="dr-wilson",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test2.jpg",
    )

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course with the first instructor
    course = Course.objects.create(
        name="Biology 101",
        description="Basic biology",
        semester=semester,
        instructor=staff1,
    )

    # Verify the first instructor is a leader
    assert user1 in course.leaders.all()
    assert course.leaders.count() == 1

    # Change the instructor
    course.instructor = staff2
    course.save()

    # Verify both instructors are now leaders (old one remains, new one is added)
    assert user1 in course.leaders.all()
    assert user2 in course.leaders.all()
    assert course.leaders.count() == 2


# ============================================================================
# Semester Visibility Tests
# ============================================================================


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
def test_semester_list_hides_invisible_from_non_staff():
    """Test that non-staff users cannot see invisible semesters in the semester list."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create visible and invisible semesters
    visible_semester = Semester.objects.create(
        name="Visible Semester",
        slug="visible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=True,
    )
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=(timezone.now() + timedelta(days=120)).date(),
        end_date=(timezone.now() + timedelta(days=210)).date(),
        visible=False,
    )

    client.login(username="student", password="password")
    url = reverse("courses:semester_list")
    response = client.get(url)

    content = response.content.decode()
    assert "Visible Semester" in content
    assert "Invisible Semester" not in content

    # Verify the context
    semesters = response.context["semesters"]
    semester_names = [s.name for s in semesters]
    assert visible_semester.name in semester_names
    assert invisible_semester.name not in semester_names


@pytest.mark.django_db
def test_semester_list_shows_all_to_staff():
    """Test that staff users can see all semesters including invisible ones."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create visible and invisible semesters
    visible_semester = Semester.objects.create(
        name="Visible Semester",
        slug="visible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=True,
    )
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=(timezone.now() + timedelta(days=120)).date(),
        end_date=(timezone.now() + timedelta(days=210)).date(),
        visible=False,
    )

    client.login(username="staff", password="password")
    url = reverse("courses:semester_list")
    response = client.get(url)

    content = response.content.decode()
    assert "Visible Semester" in content
    assert "Invisible Semester" in content

    # Verify the context
    semesters = response.context["semesters"]
    semester_names = [s.name for s in semesters]
    assert visible_semester.name in semester_names
    assert invisible_semester.name in semester_names


@pytest.mark.django_db
def test_course_list_invisible_semester_non_staff_404():
    """Test that non-staff users get 404 when accessing course list for invisible semester."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create an invisible semester
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )

    client.login(username="student", password="password")
    url = reverse("courses:course_list", kwargs={"slug": invisible_semester.slug})
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_course_list_invisible_semester_staff_access():
    """Test that staff users can access course list for invisible semesters."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create an invisible semester with a course
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )
    Course.objects.create(
        name="Test Course",
        description="Test",
        semester=invisible_semester,
        is_club=False,
    )

    client.login(username="staff", password="password")
    url = reverse("courses:course_list", kwargs={"slug": invisible_semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    assert "Test Course" in response.content.decode()


@pytest.mark.django_db
def test_course_detail_invisible_semester_non_staff_denied():
    """Test that non-staff users cannot access courses in invisible semesters."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create an invisible semester
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )

    # Create a course and enroll the student
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=invisible_semester,
        is_club=False,
    )
    student = Student.objects.create(user=user, semester=invisible_semester)
    course.students.add(student)

    client.login(username="student", password="password")
    url = reverse("courses:course_detail", kwargs={"pk": course.pk})
    response = client.get(url)

    # Should get 403 even though student is enrolled
    assert response.status_code == 403


@pytest.mark.django_db
def test_course_detail_invisible_semester_staff_access():
    """Test that staff users can access courses in invisible semesters."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create an invisible semester
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )

    # Create a course
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=invisible_semester,
        is_club=False,
    )

    client.login(username="staff", password="password")
    url = reverse("courses:course_detail", kwargs={"pk": course.pk})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_catalog_root_skips_invisible_for_non_staff():
    """Test that catalog root redirects to the most recent visible semester for non-staff."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create semesters (most recent is invisible)
    older_visible = Semester.objects.create(
        name="Older Visible",
        slug="older",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )
    Semester.objects.create(
        name="Newer Invisible",
        slug="newer",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )

    client.login(username="student", password="password")
    url = reverse("courses:catalog_root")
    response = client.get(url)

    # Should redirect to the older visible semester
    assert response.status_code == 302
    assert response.url == reverse(
        "courses:course_list", kwargs={"slug": older_visible.slug}
    )


@pytest.mark.django_db
def test_catalog_root_includes_invisible_for_staff():
    """Test that catalog root redirects to the most recent semester (even if invisible) for staff."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create semesters (most recent is invisible)
    Semester.objects.create(
        name="Older Visible",
        slug="older",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )
    newer_invisible = Semester.objects.create(
        name="Newer Invisible",
        slug="newer",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )

    client.login(username="staff", password="password")
    url = reverse("courses:catalog_root")
    response = client.get(url)

    # Should redirect to the newer invisible semester
    assert response.status_code == 302
    assert response.url == reverse(
        "courses:course_list", kwargs={"slug": newer_invisible.slug}
    )


@pytest.mark.django_db
def test_course_list_navigation_skips_invisible_for_non_staff():
    """Test that previous/next semester navigation skips invisible semesters for non-staff."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create three semesters: visible, invisible, visible
    older_visible = Semester.objects.create(
        name="Older Visible",
        slug="older",
        start_date=(timezone.now() - timedelta(days=200)).date(),
        end_date=(timezone.now() - timedelta(days=110)).date(),
        visible=True,
    )
    # Create middle invisible semester (not used directly, but necessary for test)
    Semester.objects.create(
        name="Middle Invisible",
        slug="middle",
        start_date=(timezone.now() - timedelta(days=100)).date(),
        end_date=(timezone.now() - timedelta(days=10)).date(),
        visible=False,
    )
    newer_visible = Semester.objects.create(
        name="Newer Visible",
        slug="newer",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=True,
    )

    client.login(username="student", password="password")

    # Access the newer visible semester
    url = reverse("courses:course_list", kwargs={"slug": newer_visible.slug})
    response = client.get(url)

    # Previous semester should skip the invisible one and go to older visible
    assert response.context["prev_semester"] == older_visible
    assert response.context["next_semester"] is None

    # Access the older visible semester
    url = reverse("courses:course_list", kwargs={"slug": older_visible.slug})
    response = client.get(url)

    # Next semester should skip the invisible one and go to newer visible
    assert response.context["prev_semester"] is None
    assert response.context["next_semester"] == newer_visible


@pytest.mark.django_db
def test_course_list_navigation_includes_invisible_for_staff():
    """Test that previous/next semester navigation includes invisible semesters for staff."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create three semesters: visible, invisible, visible
    older_visible = Semester.objects.create(
        name="Older Visible",
        slug="older",
        start_date=(timezone.now() - timedelta(days=200)).date(),
        end_date=(timezone.now() - timedelta(days=110)).date(),
        visible=True,
    )
    middle_invisible = Semester.objects.create(
        name="Middle Invisible",
        slug="middle",
        start_date=(timezone.now() - timedelta(days=100)).date(),
        end_date=(timezone.now() - timedelta(days=10)).date(),
        visible=False,
    )
    newer_visible = Semester.objects.create(
        name="Newer Visible",
        slug="newer",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=True,
    )

    client.login(username="staff", password="password")

    # Access the newer visible semester
    url = reverse("courses:course_list", kwargs={"slug": newer_visible.slug})
    response = client.get(url)

    # Previous semester should include the invisible one
    assert response.context["prev_semester"] == middle_invisible
    assert response.context["next_semester"] is None

    # Access the middle invisible semester
    url = reverse("courses:course_list", kwargs={"slug": middle_invisible.slug})
    response = client.get(url)

    # Should see both neighbors
    assert response.context["prev_semester"] == older_visible
    assert response.context["next_semester"] == newer_visible


# ============================================================================
# Sorting Hat View Tests
# ============================================================================


@pytest.mark.django_db
def test_sorting_hat_requires_superuser():
    """Test that only superusers can access the Sorting Hat view."""
    client = Client()

    # Test with non-authenticated user
    url = reverse("courses:sorting_hat")
    response = client.get(url)
    assert response.status_code == 302
    assert "/login/" in response.url

    # Test with regular user
    User.objects.create_user(username="regular", password="password")
    client.login(username="regular", password="password")
    response = client.get(url)
    assert response.status_code == 403

    # Test with staff (but not superuser)
    User.objects.create_user(username="staff", password="password", is_staff=True)
    client.login(username="staff", password="password")
    response = client.get(url)
    assert response.status_code == 403

    # Test with superuser
    User.objects.create_user(username="super", password="password", is_superuser=True)
    client.login(username="super", password="password")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_sorting_hat_get_displays_form():
    """Test that GET request displays the Sorting Hat form."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create a semester
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")
    response = client.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    # Check that all house fields are present
    content = response.content.decode()
    assert "Blob" in content
    assert "Cat" in content
    assert "Owl" in content
    assert "Red Panda" in content
    assert "Bunny" in content


@pytest.mark.django_db
def test_sorting_hat_assigns_students_to_houses():
    """Test that Sorting Hat correctly assigns students to houses."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students
    student1 = Student.objects.create(airtable_name="Alice", semester=semester)
    student2 = Student.objects.create(airtable_name="Bob", semester=semester)
    student3 = Student.objects.create(airtable_name="Charlie", semester=semester)

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Post sorting hat assignments
    response = client.post(
        url,
        {
            "semester": semester.id,
            "blob": "Alice\nBob",
            "cat": "Charlie",
            "owl": "",
            "red_panda": "",
            "bunny": "",
        },
    )

    assert response.status_code == 200
    assert "results" in response.context

    # Verify students were assigned correctly
    student1.refresh_from_db()
    student2.refresh_from_db()
    student3.refresh_from_db()

    assert student1.house == Student.House.BLOB
    assert student2.house == Student.House.BLOB
    assert student3.house == Student.House.CAT

    # Check results
    results = response.context["results"]
    assert len(results["assigned"]) == 3
    assert len(results["not_found"]) == 0


@pytest.mark.django_db
def test_sorting_hat_handles_not_found_students():
    """Test that Sorting Hat reports students that don't exist."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create one student
    student1 = Student.objects.create(airtable_name="Alice", semester=semester)

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Post sorting hat assignments with some non-existent students
    response = client.post(
        url,
        {
            "semester": semester.id,
            "blob": "Alice\nNonExistent1",
            "cat": "NonExistent2",
            "owl": "",
            "red_panda": "",
            "bunny": "",
        },
    )

    assert response.status_code == 200

    # Verify Alice was assigned
    student1.refresh_from_db()
    assert student1.house == Student.House.BLOB

    # Check results
    results = response.context["results"]
    assert len(results["assigned"]) == 1
    assert len(results["not_found"]) == 2
    assert "NonExistent1" in results["not_found"][0]
    assert "NonExistent2" in results["not_found"][1]


@pytest.mark.django_db
def test_sorting_hat_handles_whitespace():
    """Test that Sorting Hat handles whitespace and empty lines correctly."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students
    student1 = Student.objects.create(airtable_name="Alice", semester=semester)
    student2 = Student.objects.create(airtable_name="Bob", semester=semester)

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Post with whitespace and empty lines
    response = client.post(
        url,
        {
            "semester": semester.id,
            "blob": "  Alice  \n\n  Bob  \n\n",
            "cat": "",
            "owl": "",
            "red_panda": "",
            "bunny": "",
        },
    )

    assert response.status_code == 200

    # Verify both students were assigned
    student1.refresh_from_db()
    student2.refresh_from_db()

    assert student1.house == Student.House.BLOB
    assert student2.house == Student.House.BLOB

    results = response.context["results"]
    assert len(results["assigned"]) == 2
    assert len(results["not_found"]) == 0


@pytest.mark.django_db
def test_sorting_hat_query_optimization():
    """Test that Sorting Hat uses O(1) queries, not O(n)."""
    from django.test.utils import CaptureQueriesContext
    from django.db import connection

    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create many students
    num_students = 50
    student_names = [f"Student{i}" for i in range(num_students)]
    students = [
        Student(airtable_name=name, semester=semester) for name in student_names
    ]
    Student.objects.bulk_create(students)

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Assign all students to various houses
    blob_students = "\n".join(student_names[:10])
    cat_students = "\n".join(student_names[10:20])
    owl_students = "\n".join(student_names[20:30])
    red_panda_students = "\n".join(student_names[30:40])
    bunny_students = "\n".join(student_names[40:50])

    # Count queries
    with CaptureQueriesContext(connection) as context:
        response = client.post(
            url,
            {
                "semester": semester.id,
                "blob": blob_students,
                "cat": cat_students,
                "owl": owl_students,
                "red_panda": red_panda_students,
                "bunny": bunny_students,
            },
        )

    assert response.status_code == 200

    # Should use a constant number of queries regardless of student count:
    # 1. Session/auth queries (2-3)
    # 2. Fetch all students (1 SELECT)
    # 3. Bulk update students (1 UPDATE)
    # Total should be around 5-6 queries maximum
    assert len(context.captured_queries) <= 6, (
        f"Expected ≤6 queries, got {len(context.captured_queries)}. "
        f"Should be O(1), not O(n) with n={num_students}"
    )

    # Verify all students were assigned correctly
    results = response.context["results"]
    assert len(results["assigned"]) == num_students
    assert len(results["not_found"]) == 0


@pytest.mark.django_db
def test_sorting_hat_same_semester_constraint():
    """Test that Sorting Hat only assigns students from the selected semester."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create two semesters
    fall_semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    spring_semester = Semester.objects.create(
        name="Spring 2026",
        slug="sp26",
        start_date=(timezone.now() + timedelta(days=120)).date(),
        end_date=(timezone.now() + timedelta(days=210)).date(),
    )

    # Create students with same name in different semesters
    fall_alice = Student.objects.create(airtable_name="Alice", semester=fall_semester)
    spring_alice = Student.objects.create(
        airtable_name="Alice", semester=spring_semester
    )

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Assign Alice in fall semester
    response = client.post(
        url,
        {
            "semester": fall_semester.id,
            "blob": "Alice",
            "cat": "",
            "owl": "",
            "red_panda": "",
            "bunny": "",
        },
    )

    assert response.status_code == 200

    # Only fall Alice should be assigned
    fall_alice.refresh_from_db()
    spring_alice.refresh_from_db()

    assert fall_alice.house == Student.House.BLOB
    assert spring_alice.house == ""  # Should not be assigned


@pytest.mark.django_db
def test_sorting_hat_invalid_form():
    """Test that Sorting Hat handles invalid form submissions."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Post without semester
    response = client.post(
        url,
        {
            "blob": "Alice",
            "cat": "",
            "owl": "",
            "red_panda": "",
            "bunny": "",
        },
    )

    # Should re-render form with errors
    assert response.status_code == 200
    assert "form" in response.context
    assert not response.context["form"].is_valid()
