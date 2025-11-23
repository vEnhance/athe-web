from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student


@pytest.mark.django_db
def test_past_clubs_requires_login():
    """Test that past_clubs view requires authentication."""
    client = Client()

    # Create a past semester with a club
    past_semester = Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )
    Course.objects.create(
        name="Old Club",
        description="A club from the past",
        semester=past_semester,
        is_club=True,
    )

    # Try to access without logging in
    url = reverse("courses:past_clubs")
    response = client.get(url)

    # Should redirect to login page
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_past_clubs_shows_all_clubs_from_visible_ended_semesters():
    """Test that past_clubs shows all clubs from visible ended semesters."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create a past visible semester
    past_semester = Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )

    # Create clubs (user is NOT enrolled in any of these)
    club1 = Course.objects.create(
        name="Chess Club",
        description="Play chess",
        semester=past_semester,
        is_club=True,
    )
    club2 = Course.objects.create(
        name="Art Club",
        description="Create art",
        semester=past_semester,
        is_club=True,
    )

    client.login(username="student", password="password")
    url = reverse("courses:past_clubs")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Both clubs should be shown even though user is not enrolled
    assert club1.name in content
    assert club2.name in content


@pytest.mark.django_db
def test_past_clubs_excludes_invisible_semesters():
    """Test that past_clubs excludes clubs from invisible semesters."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create a past visible semester
    visible_semester = Semester.objects.create(
        name="Visible Semester",
        slug="visible",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )
    # Create a past invisible semester
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=(timezone.now() - timedelta(days=240)).date(),
        end_date=(timezone.now() - timedelta(days=150)).date(),
        visible=False,
    )

    # Create clubs in both semesters
    visible_club = Course.objects.create(
        name="Visible Club",
        description="Club in visible semester",
        semester=visible_semester,
        is_club=True,
    )
    invisible_club = Course.objects.create(
        name="Invisible Club",
        description="Club in invisible semester",
        semester=invisible_semester,
        is_club=True,
    )

    client.login(username="student", password="password")
    url = reverse("courses:past_clubs")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Only the visible semester's club should be shown
    assert visible_club.name in content
    assert invisible_club.name not in content


@pytest.mark.django_db
def test_past_clubs_excludes_active_and_future_semesters():
    """Test that past_clubs excludes clubs from active and future semesters."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create semesters: past, active, and future
    past_semester = Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )
    active_semester = Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
        visible=True,
    )
    future_semester = Semester.objects.create(
        name="Future Semester",
        slug="future",
        start_date=(timezone.now() + timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=120)).date(),
        visible=True,
    )

    # Create clubs in all semesters
    past_club = Course.objects.create(
        name="Past Club",
        description="Club in past semester",
        semester=past_semester,
        is_club=True,
    )
    active_club = Course.objects.create(
        name="Active Club",
        description="Club in active semester",
        semester=active_semester,
        is_club=True,
    )
    future_club = Course.objects.create(
        name="Future Club",
        description="Club in future semester",
        semester=future_semester,
        is_club=True,
    )

    client.login(username="student", password="password")
    url = reverse("courses:past_clubs")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Only the past semester's club should be shown
    assert past_club.name in content
    assert active_club.name not in content
    assert future_club.name not in content


@pytest.mark.django_db
def test_past_clubs_staff_can_click_all_clubs():
    """Test that staff users can click all past clubs."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create a past semester
    past_semester = Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )

    # Create a club (staff is NOT enrolled)
    club = Course.objects.create(
        name="Chess Club",
        description="Play chess",
        semester=past_semester,
        is_club=True,
    )

    client.login(username="staff", password="password")
    url = reverse("courses:past_clubs")
    response = client.get(url)

    assert response.status_code == 200
    # Check that the club is rendered as a clickable link
    past_clubs = response.context["past_clubs"]
    assert len(past_clubs) == 1
    assert past_clubs[0].is_clickable is True
    # Verify the link is in the HTML
    content = response.content.decode()
    club_url = reverse("courses:course_detail", kwargs={"pk": club.pk})
    assert f'href="{club_url}"' in content


@pytest.mark.django_db
def test_past_clubs_enrolled_student_can_click():
    """Test that students can click clubs from semesters they were enrolled in."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create a past semester
    past_semester = Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )

    # Create a student record for this user in this semester
    Student.objects.create(user=user, semester=past_semester)

    # Create a club (doesn't matter if enrolled in the club specifically,
    # just needs to be a student in the semester)
    club = Course.objects.create(
        name="Chess Club",
        description="Play chess",
        semester=past_semester,
        is_club=True,
    )

    client.login(username="student", password="password")
    url = reverse("courses:past_clubs")
    response = client.get(url)

    assert response.status_code == 200
    # Check that the club is rendered as a clickable link
    past_clubs = response.context["past_clubs"]
    assert len(past_clubs) == 1
    assert past_clubs[0].is_clickable is True
    # Verify the link is in the HTML
    content = response.content.decode()
    club_url = reverse("courses:course_detail", kwargs={"pk": club.pk})
    assert f'href="{club_url}"' in content


@pytest.mark.django_db
def test_past_clubs_non_enrolled_student_cannot_click():
    """Test that students cannot click clubs from semesters they were NOT enrolled in."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create a past semester
    past_semester = Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )

    # Create a club (user has NO student record for this semester)
    club = Course.objects.create(
        name="Chess Club",
        description="Play chess",
        semester=past_semester,
        is_club=True,
    )

    client.login(username="student", password="password")
    url = reverse("courses:past_clubs")
    response = client.get(url)

    assert response.status_code == 200
    # Check that the club is NOT rendered as a clickable link
    past_clubs = response.context["past_clubs"]
    assert len(past_clubs) == 1
    assert past_clubs[0].is_clickable is False
    # Verify no link is in the HTML for this club (should be a div, not an anchor)
    content = response.content.decode()
    club_url = reverse("courses:course_detail", kwargs={"pk": club.pk})
    assert f'href="{club_url}"' not in content
    # But the club name should still be visible
    assert club.name in content


@pytest.mark.django_db
def test_past_clubs_mixed_clickability():
    """Test that clubs have correct clickability based on semester enrollment."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create two past semesters
    enrolled_semester = Semester.objects.create(
        name="Enrolled Semester",
        slug="enrolled",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=90)).date(),
        visible=True,
    )
    not_enrolled_semester = Semester.objects.create(
        name="Not Enrolled Semester",
        slug="not_enrolled",
        start_date=(timezone.now() - timedelta(days=80)).date(),
        end_date=(timezone.now() - timedelta(days=50)).date(),
        visible=True,
    )

    # Create a student record only for the enrolled semester
    Student.objects.create(user=user, semester=enrolled_semester)

    # Create clubs in both semesters
    enrolled_club = Course.objects.create(
        name="Enrolled Club",
        description="Club in enrolled semester",
        semester=enrolled_semester,
        is_club=True,
    )
    not_enrolled_club = Course.objects.create(
        name="Not Enrolled Club",
        description="Club in not enrolled semester",
        semester=not_enrolled_semester,
        is_club=True,
    )

    client.login(username="student", password="password")
    url = reverse("courses:past_clubs")
    response = client.get(url)

    assert response.status_code == 200
    past_clubs = response.context["past_clubs"]
    assert len(past_clubs) == 2

    # Find the clubs in the response
    clubs_by_name = {c.name: c for c in past_clubs}

    # Enrolled club should be clickable
    assert clubs_by_name["Enrolled Club"].is_clickable is True
    # Not enrolled club should NOT be clickable
    assert clubs_by_name["Not Enrolled Club"].is_clickable is False

    # Verify in HTML
    content = response.content.decode()
    enrolled_club_url = reverse(
        "courses:course_detail", kwargs={"pk": enrolled_club.pk}
    )
    not_enrolled_club_url = reverse(
        "courses:course_detail", kwargs={"pk": not_enrolled_club.pk}
    )
    assert f'href="{enrolled_club_url}"' in content
    assert f'href="{not_enrolled_club_url}"' not in content


@pytest.mark.django_db
def test_past_clubs_empty_state():
    """Test that past_clubs handles the case with no past clubs."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create an active semester (not past)
    Semester.objects.create(
        name="Active Semester",
        slug="active",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
        visible=True,
    )

    client.login(username="student", password="password")
    url = reverse("courses:past_clubs")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "No clubs or events from past semesters." in content


@pytest.mark.django_db
def test_past_clubs_excludes_regular_courses():
    """Test that past_clubs only shows clubs, not regular courses."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create a past semester
    past_semester = Semester.objects.create(
        name="Past Semester",
        slug="past",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )

    # Create a club and a regular course
    club = Course.objects.create(
        name="Chess Club",
        description="Play chess",
        semester=past_semester,
        is_club=True,
    )
    course = Course.objects.create(
        name="Math 101",
        description="Learn math",
        semester=past_semester,
        is_club=False,
    )

    client.login(username="student", password="password")
    url = reverse("courses:past_clubs")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Only the club should be shown
    assert club.name in content
    assert course.name not in content
