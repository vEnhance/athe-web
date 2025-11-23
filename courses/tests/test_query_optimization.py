from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student


@pytest.mark.django_db
def test_my_courses_query_count():
    """Test that my_courses uses O(1) queries regardless of data size."""
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
