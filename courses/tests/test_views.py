from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseMeeting, Semester, Student


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
