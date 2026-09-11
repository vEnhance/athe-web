from collections.abc import Callable
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Course, CourseMeeting, GlobalEvent, Semester, Student

CALENDAR = reverse("courses:calendar")
UPCOMING = reverse("courses:upcoming")
GLOBAL_EVENTS = reverse("courses:global_events")


def detail_url(event: GlobalEvent) -> str:
    return reverse("courses:global_event_detail", kwargs={"pk": event.pk})


def calendar_events(response: HttpResponse) -> dict[str, str]:
    """Every event drawn on the month, keyed by title, valued by category."""
    return {
        event["title"]: event["category"]
        for week in response.context["weeks_data"]
        for day in week
        for event in day["events"]
    }


@pytest.fixture
def event(semester: Semester) -> GlobalEvent:
    return GlobalEvent.objects.create(
        semester=semester, title="Welcome Event", start_time=timezone.now()
    )


@pytest.fixture
def staff(athe: AtheClient, make_user: Callable[..., User]) -> User:
    return athe.login(make_user(username="staff", is_staff=True))


@pytest.mark.django_db
def test_global_event_str(event: GlobalEvent):
    assert "Welcome Event" in str(event)


@pytest.mark.django_db
def test_global_event_get_absolute_url(event: GlobalEvent):
    assert event.get_absolute_url() == f"/catalog/event/{event.pk}/"


@pytest.mark.django_db
def test_event_detail_staff_can_access(
    athe: AtheClient, event: GlobalEvent, staff: User
):
    response = athe.get_ok(detail_url(event))

    assert response.context["event"] == event
    assert athe.text_of(response, "global-event-title") == "Welcome Event"


@pytest.mark.django_db
def test_event_detail_enrolled_student_can_access(
    athe: AtheClient,
    semester: Semester,
    event: GlobalEvent,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    user = make_user()
    make_student(semester, user=user)

    athe.login(user)
    athe.get_ok(detail_url(event))


@pytest.mark.django_db
def test_event_detail_unenrolled_student_cannot_access(
    athe: AtheClient, event: GlobalEvent, make_user: Callable[..., User]
):
    athe.login(make_user())
    assert athe.get(detail_url(event)).status_code == 403


@pytest.mark.django_db
def test_event_detail_invisible_semester_blocked_for_non_staff(
    athe: AtheClient,
    semester: Semester,
    event: GlobalEvent,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    semester.visible = False
    semester.save()
    user = make_user()
    make_student(semester, user=user)

    athe.login(user)
    assert athe.get(detail_url(event)).status_code == 403


@pytest.mark.django_db
def test_event_detail_shows_link_and_description(
    athe: AtheClient, event: GlobalEvent, staff: User
):
    event.description = "This is a test event"
    event.link = "https://zoom.us/test"
    event.save()

    response = athe.get_ok(detail_url(event))

    athe.assert_testid(response, "global-event-link", "global-event-description")
    assert "This is a test event" in athe.text_of(response, "global-event-description")
    assert event.link.encode() in response.content


@pytest.mark.django_db
def test_upcoming_includes_global_events(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    user = make_user()
    make_student(semester, user=user)
    soon = GlobalEvent.objects.create(
        semester=semester,
        title="Upcoming Global Event",
        start_time=timezone.now() + timedelta(hours=1),
    )

    athe.login(user)
    response = athe.get_ok(UPCOMING)

    assert list(response.context["upcoming_events"]) == [soon]


@pytest.mark.django_db
def test_upcoming_excludes_past_events(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    user = make_user()
    make_student(semester, user=user)
    GlobalEvent.objects.create(
        semester=semester,
        title="Past Event",
        start_time=timezone.now() - timedelta(hours=1),
    )

    athe.login(user)
    response = athe.get_ok(UPCOMING)

    assert list(response.context["upcoming_events"]) == []


@pytest.mark.django_db
def test_upcoming_staff_see_events_without_enrolling(
    athe: AtheClient, semester: Semester, staff: User
):
    """Staff join no semester, so visibility cannot come from enrolment."""
    visible = GlobalEvent.objects.create(
        semester=semester,
        title="Staff Visible Event",
        start_time=timezone.now() + timedelta(hours=1),
    )

    response = athe.get_ok(UPCOMING)

    assert list(response.context["upcoming_events"]) == [visible]


@pytest.mark.django_db
def test_calendar_requires_login(athe: AtheClient):
    assert athe.get(CALENDAR).status_code == 302


@pytest.mark.django_db
def test_calendar_defaults_to_this_month(
    athe: AtheClient, make_user: Callable[..., User]
):
    athe.login(make_user())
    response = athe.get_ok(CALENDAR)

    today = timezone.localdate()
    assert response.context["display_year"] == today.year
    assert response.context["display_month"] == today.month


@pytest.mark.django_db
def test_calendar_month_navigation(athe: AtheClient, make_user: Callable[..., User]):
    athe.login(make_user())
    response = athe.get_ok(f"{CALENDAR}?year=2025&month=6")

    assert response.context["display_year"] == 2025
    assert response.context["display_month"] == 6
    assert response.context["month_name"] == "June"


@pytest.mark.django_db
def test_calendar_categorises_what_it_draws(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    """Enrolled classes, enrolled clubs, other clubs and global events are four
    different colours on the grid; a class nobody here takes is not drawn."""
    user = make_user()
    student = make_student(semester, user=user)
    soon = timezone.now() + timedelta(hours=2)

    my_class = make_course(semester, name="Test Class")
    my_class.students.add(student)
    my_club = make_course(semester, name="Test Club", is_club=True)
    my_club.students.add(student)
    other_club = make_course(semester, name="Other Club", is_club=True)
    other_class = make_course(semester, name="Other Class")
    for course in (my_class, my_club, other_club, other_class):
        CourseMeeting.objects.create(course=course, start_time=soon)
    GlobalEvent.objects.create(
        semester=semester, title="Calendar Test Event", start_time=soon
    )

    athe.login(user)
    response = athe.get_ok(CALENDAR)

    assert calendar_events(response) == {
        "Test Class": "enrolled_class",
        "Test Club": "enrolled_club",
        "Other Club": "other_club",
        "Calendar Test Event": "global",
    }


@pytest.mark.django_db
def test_cal_redirects_to_calendar(athe: AtheClient, make_user: Callable[..., User]):
    athe.login(make_user())
    athe.get_redirects(CALENDAR, "/cal/")


@pytest.mark.django_db
def test_global_event_admin_list(
    athe: AtheClient, event: GlobalEvent, make_user: Callable[..., User]
):
    athe.login(make_user(username="admin", is_staff=True, is_superuser=True))
    response = athe.get_ok("/admin/courses/globalevent/")

    assert list(response.context["cl"].result_list) == [event]


@pytest.mark.django_db
def test_global_events_list_requires_login(athe: AtheClient):
    athe.get_redirects(reverse("login"), GLOBAL_EVENTS)


@pytest.mark.django_db
def test_global_events_list_includes_past_events(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    """The page is the semester's whole programme, not just what is left."""
    user = make_user()
    make_student(semester, user=user)
    opening = GlobalEvent.objects.create(
        semester=semester,
        title="Opening Social",
        start_time=timezone.now() - timedelta(days=3),
    )
    lecture = GlobalEvent.objects.create(
        semester=semester,
        title="Guest Lecture",
        start_time=timezone.now() + timedelta(days=3),
    )

    athe.login(user)
    response = athe.get_ok(GLOBAL_EVENTS)

    assert list(response.context["events"]) == [opening, lecture]
    athe.assert_testid_count(response, "global-event-row", 2)


@pytest.mark.django_db
def test_global_events_list_excludes_semesters_the_student_is_not_in(
    athe: AtheClient,
    semester: Semester,
    past_semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    """A student who was here last term but is not enrolled now sees nothing
    of this term's programme."""
    user = make_user()
    make_student(past_semester, user=user)
    GlobalEvent.objects.create(
        semester=semester,
        title="Someone Else's Event",
        start_time=timezone.now() + timedelta(days=1),
    )

    athe.login(user)
    response = athe.get_ok(GLOBAL_EVENTS)

    assert list(response.context["events"]) == []
    athe.assert_testid(response, "global-events-empty")


@pytest.mark.django_db
def test_global_events_list_staff_see_every_active_semester(
    athe: AtheClient, semester: Semester, staff: User
):
    visible = GlobalEvent.objects.create(
        semester=semester,
        title="Staff Visible Event",
        start_time=timezone.now() + timedelta(days=1),
    )

    response = athe.get_ok(GLOBAL_EVENTS)

    assert list(response.context["events"]) == [visible]
