from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Course, CourseMeeting, Semester

EASTERN = ZoneInfo("America/New_York")


@pytest.fixture
def course(
    make_semester: Callable[..., Semester], make_course: Callable[..., Course]
) -> Course:
    fall = make_semester(
        name="Fall 2025", start_date=date(2025, 9, 1), end_date=date(2025, 12, 15)
    )
    return make_course(fall, name="Test Course")


@pytest.fixture
def leader(
    athe: AtheClient,
    course: Course,
    make_user: Callable[..., User],
    make_staff_listing,
) -> User:
    user = make_user(username="leader")
    course.instructor = make_staff_listing(user)
    course.save()
    return athe.login(user)


@pytest.mark.django_db
def test_manage_meetings_offers_recurring_generator(
    athe: AtheClient, course: Course, leader: User
):
    """The client-side quick-fill controls and their script are on the page."""
    url = reverse("courses:manage_meetings", kwargs={"pk": course.pk})
    response = athe.get_ok(url)

    athe.assert_testid(response, "recurring-panel", "recurring-generate")
    # manage_meetings.js reads the term's end date off the panel to guess how
    # many meetings fit, so the attribute itself is the contract here.
    assert b'data-semester-end="2025-12-15"' in response.content
    assert b"js/manage_meetings.js" in response.content


@pytest.mark.django_db
def test_manage_meetings_saves_a_generated_weekly_batch(
    athe: AtheClient, course: Course, leader: User
):
    """A batch of rows like the generator produces round-trips through the formset.

    The generator is purely client-side, so what it POSTs is an ordinary
    formset of new meetings. The run below straddles the November change off
    daylight saving: a 4:00pm class must stay at 4:00pm Eastern every week,
    which means the stored UTC times shift by an hour partway through.
    """
    starts = [
        "2025-10-29T16:00",
        "2025-11-05T16:00",
        "2025-11-12T16:00",
        "2025-11-19T16:00",
    ]
    data = {
        "form-TOTAL_FORMS": str(len(starts)),
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
    }
    for i, start in enumerate(starts):
        data[f"form-{i}-id"] = ""
        data[f"form-{i}-start_time"] = start
        data[f"form-{i}-title"] = f"Week {i + 1}"

    url = reverse("courses:manage_meetings", kwargs={"pk": course.pk})
    athe.post_redirects(url, url, data)

    meetings = list(CourseMeeting.objects.filter(course=course).order_by("start_time"))
    assert [m.title for m in meetings] == ["Week 1", "Week 2", "Week 3", "Week 4"]
    assert [m.start_time.astimezone(EASTERN) for m in meetings] == [
        datetime(2025, 10, 29, 16, 0, tzinfo=EASTERN),
        datetime(2025, 11, 5, 16, 0, tzinfo=EASTERN),
        datetime(2025, 11, 12, 16, 0, tzinfo=EASTERN),
        datetime(2025, 11, 19, 16, 0, tzinfo=EASTERN),
    ]
