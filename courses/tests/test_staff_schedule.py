from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseMeeting, Semester


def make_semester(*, active: bool = True) -> Semester:
    today = timezone.now().date()
    if active:
        start, end = today - timedelta(days=30), today + timedelta(days=60)
    else:
        start, end = today - timedelta(days=120), today - timedelta(days=30)
    return Semester.objects.create(
        name="Test Semester",
        slug="test-sem",
        start_date=start,
        end_date=end,
    )


@pytest.fixture()
def staff_client():
    user = User.objects.create_user(username="staff", password="pw", is_staff=True)
    c = Client()
    c.login(username="staff", password="pw")
    return c, user


@pytest.fixture()
def plain_client():
    User.objects.create_user(username="student", password="pw")
    c = Client()
    c.login(username="student", password="pw")
    return c


# ── access control ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_non_staff_redirected(plain_client):
    make_semester()
    url = reverse("courses:staff_schedule")
    response = plain_client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_unauthenticated_redirected():
    make_semester()
    url = reverse("courses:staff_schedule")
    response = Client().get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_staff_can_access(staff_client):
    make_semester()
    client, _ = staff_client
    url = reverse("courses:staff_schedule")
    response = client.get(url)
    assert response.status_code == 200


# ── no active semester ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_no_active_semester_shows_error(staff_client):
    # Create a past semester so there is something in the DB but no active one
    make_semester(active=False)
    client, _ = staff_client
    url = reverse("courses:staff_schedule")
    response = client.get(url)
    assert response.status_code == 200
    assert b"no currently active semester" in response.content.lower()


# ── slug-based URL ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_slug_url_shows_correct_semester(staff_client):
    sem = make_semester(active=False)
    client, _ = staff_client
    url = reverse("courses:staff_schedule_semester", kwargs={"slug": sem.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert sem.name.encode() in response.content


@pytest.mark.django_db
def test_slug_url_404_for_unknown_slug(staff_client):
    client, _ = staff_client
    url = reverse("courses:staff_schedule_semester", kwargs={"slug": "does-not-exist"})
    response = client.get(url)
    assert response.status_code == 404


# ── meeting data ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_class_meetings_appear(staff_client):
    sem = make_semester()
    course = Course.objects.create(
        name="Algebra", description="", semester=sem, is_club=False
    )
    CourseMeeting.objects.create(
        course=course, start_time=timezone.now() + timedelta(days=1), title="Session 1"
    )
    client, _ = staff_client
    response = client.get(reverse("courses:staff_schedule"))
    assert b"Algebra" in response.content
    assert b"Session 1" in response.content


@pytest.mark.django_db
def test_club_meetings_appear(staff_client):
    sem = make_semester()
    club = Course.objects.create(
        name="Chess Club", description="", semester=sem, is_club=True
    )
    CourseMeeting.objects.create(
        course=club, start_time=timezone.now() + timedelta(days=1), title="Match Day"
    )
    client, _ = staff_client
    response = client.get(reverse("courses:staff_schedule"))
    assert b"Chess Club" in response.content
    assert b"Match Day" in response.content


@pytest.mark.django_db
def test_class_and_club_meetings_are_separated(staff_client):
    """Meetings for classes and clubs don't bleed into each other's tables."""
    sem = make_semester()
    course = Course.objects.create(
        name="Biology", description="", semester=sem, is_club=False
    )
    club = Course.objects.create(
        name="Art Club", description="", semester=sem, is_club=True
    )
    CourseMeeting.objects.create(
        course=course, start_time=timezone.now() + timedelta(days=1)
    )
    CourseMeeting.objects.create(
        course=club, start_time=timezone.now() + timedelta(days=2)
    )
    client, _ = staff_client
    response = client.get(reverse("courses:staff_schedule"))
    ctx = response.context
    class_course_ids = {m.course_id for m in ctx["class_meetings"]}
    club_course_ids = {m.course_id for m in ctx["club_meetings"]}
    assert course.pk in class_course_ids
    assert club.pk not in class_course_ids
    assert club.pk in club_course_ids
    assert course.pk not in club_course_ids


# ── courses without meetings ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_course_without_meetings_listed(staff_client):
    sem = make_semester()
    Course.objects.create(
        name="Empty Class", description="", semester=sem, is_club=False
    )
    client, _ = staff_client
    response = client.get(reverse("courses:staff_schedule"))
    assert b"Empty Class" in response.content
    ctx = response.context
    assert any(c.name == "Empty Class" for c in ctx["classes_without_meetings"])


@pytest.mark.django_db
def test_course_with_meetings_not_in_without_meetings_list(staff_client):
    sem = make_semester()
    course = Course.objects.create(
        name="Full Class", description="", semester=sem, is_club=False
    )
    CourseMeeting.objects.create(
        course=course, start_time=timezone.now() + timedelta(days=1)
    )
    client, _ = staff_client
    response = client.get(reverse("courses:staff_schedule"))
    ctx = response.context
    assert not any(c.name == "Full Class" for c in ctx["classes_without_meetings"])


# ── sorting ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_sort_by_course(staff_client):
    sem = make_semester()
    c1 = Course.objects.create(name="Zebra Course", description="", semester=sem)
    c2 = Course.objects.create(name="Alpha Course", description="", semester=sem)
    CourseMeeting.objects.create(
        course=c1, start_time=timezone.now() + timedelta(days=1)
    )
    CourseMeeting.objects.create(
        course=c2, start_time=timezone.now() + timedelta(days=2)
    )
    client, _ = staff_client
    response = client.get(reverse("courses:staff_schedule") + "?sort=course")
    meetings = response.context["class_meetings"]
    names = [m.course.name for m in meetings]
    assert names == sorted(names)


@pytest.mark.django_db
def test_sort_by_date(staff_client):
    sem = make_semester()
    c1 = Course.objects.create(name="Alpha Course", description="", semester=sem)
    c2 = Course.objects.create(name="Zebra Course", description="", semester=sem)
    t1 = timezone.now() + timedelta(days=5)
    t2 = timezone.now() + timedelta(days=1)
    CourseMeeting.objects.create(course=c1, start_time=t1)
    CourseMeeting.objects.create(course=c2, start_time=t2)
    client, _ = staff_client
    response = client.get(reverse("courses:staff_schedule") + "?sort=date")
    meetings = response.context["class_meetings"]
    times = [m.start_time for m in meetings]
    assert times == sorted(times)
