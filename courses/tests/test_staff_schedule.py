from collections.abc import Callable
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Course, CourseMeeting, Semester

SCHEDULE = reverse("courses:staff_schedule")


@pytest.fixture
def staff(athe: AtheClient, make_user: Callable[..., User]) -> User:
    return athe.login(make_user(username="staff", is_staff=True))


def meeting(course: Course, days: int, title: str = "") -> CourseMeeting:
    return CourseMeeting.objects.create(
        course=course, start_time=timezone.now() + timedelta(days=days), title=title
    )


@pytest.mark.django_db
def test_non_staff_redirected(
    athe: AtheClient, semester: Semester, make_user: Callable[..., User]
):
    athe.login(make_user())
    athe.get_redirects(reverse("courses:catalog_root"), SCHEDULE)


@pytest.mark.django_db
def test_unauthenticated_redirected(athe: AtheClient, semester: Semester):
    assert athe.get(SCHEDULE).status_code == 302


@pytest.mark.django_db
def test_staff_schedule_defaults_to_the_current_semester(
    athe: AtheClient, semester: Semester, staff: User
):
    response = athe.get_ok(SCHEDULE)

    assert response.context["semester"] == semester


@pytest.mark.django_db
def test_no_current_semester_shows_error(
    athe: AtheClient, past_semester: Semester, staff: User
):
    """Only an ended semester on the books, so there is nothing to default to."""
    response = athe.get_ok(SCHEDULE)

    athe.assert_testid(response, "schedule-error")
    assert response.context["all_semesters"] == [past_semester]


@pytest.mark.django_db
def test_slug_url_shows_correct_semester(
    athe: AtheClient, past_semester: Semester, staff: User
):
    url = reverse(
        "courses:staff_schedule_semester", kwargs={"slug": past_semester.slug}
    )
    response = athe.get_ok(url)

    assert response.context["semester"] == past_semester


@pytest.mark.django_db
def test_slug_url_404_for_unknown_slug(athe: AtheClient, staff: User):
    url = reverse("courses:staff_schedule_semester", kwargs={"slug": "does-not-exist"})
    assert athe.get(url).status_code == 404


@pytest.mark.django_db
def test_class_and_club_meetings_are_separated(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    """Meetings for classes and clubs don't bleed into each other's tables."""
    biology = make_course(semester, name="Biology")
    art_club = make_course(semester, name="Art Club", is_club=True)
    class_meeting = meeting(biology, 1, "Session 1")
    club_meeting = meeting(art_club, 2, "Match Day")

    response = athe.get_ok(SCHEDULE)

    assert response.context["class_meetings"] == [class_meeting]
    assert response.context["club_meetings"] == [club_meeting]


@pytest.mark.django_db
def test_courses_without_meetings_are_listed_separately(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    """An empty class is the one worth chasing, so it gets its own list."""
    empty = make_course(semester, name="Empty Class")
    full = make_course(semester, name="Full Class")
    empty_club = make_course(semester, name="Empty Club", is_club=True)
    meeting(full, 1)

    response = athe.get_ok(SCHEDULE)

    assert response.context["classes_without_meetings"] == [empty]
    assert response.context["clubs_without_meetings"] == [empty_club]


@pytest.mark.django_db
def test_sort_by_course(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    meeting(make_course(semester, name="Zebra Course"), 1)
    meeting(make_course(semester, name="Alpha Course"), 2)

    response = athe.get_ok(f"{SCHEDULE}?sort=course")

    names = [m.course.name for m in response.context["class_meetings"]]
    assert names == ["Alpha Course", "Zebra Course"]


@pytest.mark.django_db
def test_sort_by_date(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    later = meeting(make_course(semester, name="Alpha Course"), 5)
    sooner = meeting(make_course(semester, name="Zebra Course"), 1)

    response = athe.get_ok(f"{SCHEDULE}?sort=date")

    assert response.context["class_meetings"] == [sooner, later]


@pytest.mark.django_db
def test_default_shows_two_weeks(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    soon = meeting(make_course(semester, name="Soon Course"), 3)
    meeting(make_course(semester, name="Distant Course"), 20)

    response = athe.get_ok(SCHEDULE)

    assert response.context["horizon"] == "2"
    assert response.context["class_meetings"] == [soon]


@pytest.mark.django_db
def test_future_horizon_keeps_every_upcoming_meeting(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    course = make_course(semester)
    meeting(course, -5)
    soon = meeting(course, 3)
    distant = meeting(course, 70)

    response = athe.get_ok(f"{SCHEDULE}?sort=date&weeks=future")

    assert response.context["class_meetings"] == [soon, distant]


@pytest.mark.django_db
def test_all_horizon_keeps_the_past_too(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    course = make_course(semester)
    past = meeting(course, -5)
    soon = meeting(course, 3)
    distant = meeting(course, 70)

    response = athe.get_ok(f"{SCHEDULE}?sort=date&weeks=all")

    assert response.context["class_meetings"] == [past, soon, distant]


@pytest.mark.django_db
def test_weeks_widens_the_window(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    course = make_course(semester)
    soon = meeting(course, 3)
    distant = meeting(course, 20)
    meeting(course, 70)

    response = athe.get_ok(f"{SCHEDULE}?sort=date&weeks=4")

    assert response.context["horizon"] == "4"
    assert response.context["class_meetings"] == [soon, distant]


@pytest.mark.django_db
def test_window_excludes_meetings_already_past(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    course = make_course(semester)
    meeting(course, -3)
    upcoming = meeting(course, 3)

    response = athe.get_ok(SCHEDULE)

    assert response.context["class_meetings"] == [upcoming]


@pytest.mark.parametrize("value", ["", "0", "seven", "-3", "99", "ALL"])
@pytest.mark.django_db
def test_unusable_horizon_falls_back_to_the_default(
    athe: AtheClient, semester: Semester, staff: User, value: str
):
    response = athe.get_ok(f"{SCHEDULE}?weeks={value}")

    assert response.context["horizon"] == "2"


@pytest.mark.django_db
def test_window_of_a_finished_semester_opens_at_its_start(
    athe: AtheClient,
    past_semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    """Today is past this semester, so its first weeks are the useful ones."""
    course = make_course(past_semester)
    opening = meeting(course, -118)
    meeting(course, -35)

    url = reverse(
        "courses:staff_schedule_semester", kwargs={"slug": past_semester.slug}
    )
    response = athe.get_ok(url)

    assert response.context["class_meetings"] == [opening]


@pytest.mark.django_db
def test_horizon_does_not_change_the_no_meetings_list(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_course: Callable[..., Course],
):
    """Having meetings at all is a fact about the semester, not the horizon."""
    later = make_course(semester, name="Later Course")
    empty = make_course(semester, name="Empty Course")
    meeting(later, 20)

    response = athe.get_ok(SCHEDULE)

    assert response.context["class_meetings"] == []
    assert response.context["classes_without_meetings"] == [empty]
