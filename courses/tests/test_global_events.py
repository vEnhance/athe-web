from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseMeeting, GlobalEvent, Semester, Student


@pytest.mark.django_db
class TestGlobalEventModel:
    def test_global_event_str(self):
        """Test GlobalEvent string representation."""
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
        )
        event = GlobalEvent.objects.create(
            semester=semester,
            title="Welcome Event",
            start_time=timezone.now(),
        )
        assert "Welcome Event" in str(event)

    def test_global_event_get_absolute_url(self):
        """Test GlobalEvent get_absolute_url method."""
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
        )
        event = GlobalEvent.objects.create(
            semester=semester,
            title="Welcome Event",
            start_time=timezone.now(),
        )
        url = event.get_absolute_url()
        assert f"/catalog/event/{event.pk}/" in url


@pytest.mark.django_db
class TestGlobalEventDetailView:
    def test_staff_can_access(self):
        """Test that staff can access global event detail view."""
        client = Client()
        User.objects.create_user(username="staff", password="password", is_staff=True)
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
        )
        event = GlobalEvent.objects.create(
            semester=semester,
            title="Welcome Event",
            start_time=timezone.now(),
        )

        client.login(username="staff", password="password")
        response = client.get(
            reverse("courses:global_event_detail", kwargs={"pk": event.pk})
        )
        assert response.status_code == 200
        assert "Welcome Event" in response.content.decode()

    def test_enrolled_student_can_access(self):
        """Test that students enrolled in the semester can access."""
        client = Client()
        user = User.objects.create_user(username="student", password="password")
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
        )
        Student.objects.create(
            user=user, semester=semester, airtable_name="Test Student"
        )
        event = GlobalEvent.objects.create(
            semester=semester,
            title="Welcome Event",
            start_time=timezone.now(),
        )

        client.login(username="student", password="password")
        response = client.get(
            reverse("courses:global_event_detail", kwargs={"pk": event.pk})
        )
        assert response.status_code == 200

    def test_unenrolled_student_cannot_access(self):
        """Test that students not enrolled in the semester cannot access."""
        client = Client()
        User.objects.create_user(username="student", password="password")
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
        )
        event = GlobalEvent.objects.create(
            semester=semester,
            title="Welcome Event",
            start_time=timezone.now(),
        )

        client.login(username="student", password="password")
        response = client.get(
            reverse("courses:global_event_detail", kwargs={"pk": event.pk})
        )
        assert response.status_code == 403

    def test_invisible_semester_blocked_for_non_staff(self):
        """Test that events in invisible semesters are blocked for non-staff."""
        client = Client()
        user = User.objects.create_user(username="student", password="password")
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
            visible=False,
        )
        Student.objects.create(
            user=user, semester=semester, airtable_name="Test Student"
        )
        event = GlobalEvent.objects.create(
            semester=semester,
            title="Welcome Event",
            start_time=timezone.now(),
        )

        client.login(username="student", password="password")
        response = client.get(
            reverse("courses:global_event_detail", kwargs={"pk": event.pk})
        )
        assert response.status_code == 403

    def test_event_with_link_and_description(self):
        """Test that event link and description are displayed."""
        client = Client()
        User.objects.create_user(username="staff", password="password", is_staff=True)
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
        )
        event = GlobalEvent.objects.create(
            semester=semester,
            title="Welcome Event",
            start_time=timezone.now(),
            description="This is a test event",
            link="https://zoom.us/test",
        )

        client.login(username="staff", password="password")
        response = client.get(
            reverse("courses:global_event_detail", kwargs={"pk": event.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "This is a test event" in content
        assert "https://zoom.us/test" in content


@pytest.mark.django_db
class TestUpcomingView:
    def test_upcoming_includes_global_events(self):
        """Test that upcoming view includes global events."""
        client = Client()
        user = User.objects.create_user(username="student", password="password")
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
        )
        Student.objects.create(
            user=user, semester=semester, airtable_name="Test Student"
        )
        GlobalEvent.objects.create(
            semester=semester,
            title="Upcoming Global Event",
            start_time=timezone.now() + timedelta(hours=1),
        )

        client.login(username="student", password="password")
        response = client.get(reverse("courses:upcoming"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Upcoming Global Event" in content
        assert "Global" in content

    def test_upcoming_excludes_past_events(self):
        """Test that past events are not shown in upcoming."""
        client = Client()
        user = User.objects.create_user(username="student", password="password")
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
        )
        Student.objects.create(
            user=user, semester=semester, airtable_name="Test Student"
        )
        GlobalEvent.objects.create(
            semester=semester,
            title="Past Event",
            start_time=timezone.now() - timedelta(hours=1),
        )

        client.login(username="student", password="password")
        response = client.get(reverse("courses:upcoming"))
        assert response.status_code == 200
        assert "Past Event" not in response.content.decode()

    def test_staff_sees_all_visible_semester_events(self):
        """Test that staff can see events from all visible semesters."""
        client = Client()
        User.objects.create_user(username="staff", password="password", is_staff=True)
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
        )
        GlobalEvent.objects.create(
            semester=semester,
            title="Staff Visible Event",
            start_time=timezone.now() + timedelta(hours=1),
        )

        client.login(username="staff", password="password")
        response = client.get(reverse("courses:upcoming"))
        assert response.status_code == 200
        assert "Staff Visible Event" in response.content.decode()


@pytest.mark.django_db
class TestCalendarView:
    def test_calendar_view_accessible(self):
        """Test that calendar view is accessible to logged in users."""
        client = Client()
        User.objects.create_user(username="user", password="password")
        client.login(username="user", password="password")
        response = client.get(reverse("courses:calendar"))
        assert response.status_code == 200
        assert "Calendar" in response.content.decode()

    def test_calendar_view_shows_events(self):
        """Test that calendar view shows events."""
        client = Client()
        user = User.objects.create_user(username="student", password="password")
        today = timezone.now().date()
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=today,
            end_date=today + timedelta(days=90),
        )
        Student.objects.create(
            user=user, semester=semester, airtable_name="Test Student"
        )
        # Create event for today
        GlobalEvent.objects.create(
            semester=semester,
            title="Calendar Test Event",
            start_time=timezone.now() + timedelta(hours=2),
        )

        client.login(username="student", password="password")
        response = client.get(reverse("courses:calendar"))
        assert response.status_code == 200
        assert "Calendar Test Event" in response.content.decode()

    def test_calendar_month_navigation(self):
        """Test calendar month navigation with query parameter."""
        client = Client()
        User.objects.create_user(username="user", password="password")
        client.login(username="user", password="password")

        # Navigate to next month
        response = client.get(reverse("courses:calendar") + "?year=2025&month=6")
        assert response.status_code == 200
        assert "June 2025" in response.content.decode()

    def test_calendar_shows_enrolled_classes(self):
        """Test that calendar shows enrolled class meetings."""
        client = Client()
        user = User.objects.create_user(username="student", password="password")
        today = timezone.now().date()
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=today,
            end_date=today + timedelta(days=90),
        )
        student = Student.objects.create(
            user=user, semester=semester, airtable_name="Test Student"
        )
        course = Course.objects.create(
            name="Test Class",
            semester=semester,
            description="Test",
            is_club=False,
        )
        course.students.add(student)
        CourseMeeting.objects.create(
            course=course,
            title="Class Meeting",
            start_time=timezone.now() + timedelta(hours=2),
        )

        client.login(username="student", password="password")
        response = client.get(reverse("courses:calendar"))
        assert response.status_code == 200
        assert "Test Class" in response.content.decode()

    def test_calendar_shows_enrolled_clubs(self):
        """Test that calendar shows enrolled club meetings."""
        client = Client()
        user = User.objects.create_user(username="student", password="password")
        today = timezone.now().date()
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=today,
            end_date=today + timedelta(days=90),
        )
        student = Student.objects.create(
            user=user, semester=semester, airtable_name="Test Student"
        )
        club = Course.objects.create(
            name="Test Club",
            semester=semester,
            description="Test",
            is_club=True,
        )
        club.students.add(student)
        CourseMeeting.objects.create(
            course=club,
            title="Club Meeting",
            start_time=timezone.now() + timedelta(hours=2),
        )

        client.login(username="student", password="password")
        response = client.get(reverse("courses:calendar"))
        assert response.status_code == 200
        assert "Test Club" in response.content.decode()

    def test_calendar_shows_other_clubs(self):
        """Test that calendar shows other club meetings (not enrolled)."""
        client = Client()
        user = User.objects.create_user(username="student", password="password")
        today = timezone.now().date()
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=today,
            end_date=today + timedelta(days=90),
        )
        Student.objects.create(
            user=user, semester=semester, airtable_name="Test Student"
        )
        club = Course.objects.create(
            name="Other Club",
            semester=semester,
            description="Test",
            is_club=True,
        )
        CourseMeeting.objects.create(
            course=club,
            title="Other Club Meeting",
            start_time=timezone.now() + timedelta(hours=2),
        )

        client.login(username="student", password="password")
        response = client.get(reverse("courses:calendar"))
        assert response.status_code == 200
        # The "other club" should appear in the HTML (with other_club category)
        assert "Other Club" in response.content.decode()

    def test_calendar_requires_login(self):
        """Test that calendar view requires login."""
        client = Client()
        response = client.get(reverse("courses:calendar"))
        assert response.status_code == 302  # Redirects to login


@pytest.mark.django_db
class TestCalRedirect:
    def test_cal_redirects_to_calendar(self):
        """Test that /cal redirects to /catalog/calendar."""
        client = Client()
        User.objects.create_user(username="user", password="password")
        client.login(username="user", password="password")
        response = client.get("/cal/")
        assert response.status_code == 302
        assert "/catalog/calendar/" in response.url


@pytest.mark.django_db
class TestGlobalEventInAdmin:
    def test_global_event_admin_list(self):
        """Test that global events appear in admin."""
        client = Client()
        User.objects.create_superuser(username="admin", password="password")
        semester = Semester.objects.create(
            name="Fall 2025",
            slug="fa25",
            start_date=timezone.now().date(),
            end_date=(timezone.now() + timedelta(days=90)).date(),
        )
        GlobalEvent.objects.create(
            semester=semester,
            title="Admin Test Event",
            start_time=timezone.now(),
        )

        client.login(username="admin", password="password")
        response = client.get("/admin/courses/globalevent/")
        assert response.status_code == 200
        assert "Admin Test Event" in response.content.decode()
