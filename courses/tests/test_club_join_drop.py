from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student


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
def test_join_club_fails_for_non_student():
    """Test that joining a club fails if a Student record if it doesn't exist."""
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
    assert response.status_code == 302
    assert response.url == reverse("courses:my_clubs")


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
