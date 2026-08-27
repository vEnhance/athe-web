from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from courses.models import Course, CourseMeeting, Semester

EASTERN = ZoneInfo("America/New_York")


@pytest.fixture
def course() -> Course:
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=date(2025, 9, 1),
        end_date=date(2025, 12, 15),
    )
    return Course.objects.create(name="Test Course", description="Test", semester=fall)


@pytest.fixture
def leader_client(course: Course) -> Client:
    user = User.objects.create_user(username="leader", password="password")
    course.leaders.add(user)
    client = Client()
    client.login(username="leader", password="password")
    return client


@pytest.mark.django_db
def test_manage_meetings_offers_recurring_generator(
    course: Course, leader_client: Client
):
    """The client-side quick-fill controls and their script are on the page."""
    url = reverse("courses:manage_meetings", kwargs={"pk": course.pk})
    response = leader_client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert 'id="recurring-panel"' in content
    assert 'id="recurring-generate-btn"' in content
    # The generator reads the term's end date to guess how many meetings fit.
    assert 'data-semester-end="2025-12-15"' in content
    assert "js/manage_meetings.js" in content


@pytest.mark.django_db
def test_manage_meetings_saves_a_generated_weekly_batch(
    course: Course, leader_client: Client
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
    response = leader_client.post(url, data)

    assert response.status_code == 302
    meetings = list(CourseMeeting.objects.filter(course=course).order_by("start_time"))
    assert [m.title for m in meetings] == ["Week 1", "Week 2", "Week 3", "Week 4"]
    assert [m.start_time.astimezone(EASTERN) for m in meetings] == [
        datetime(2025, 10, 29, 16, 0, tzinfo=EASTERN),
        datetime(2025, 11, 5, 16, 0, tzinfo=EASTERN),
        datetime(2025, 11, 12, 16, 0, tzinfo=EASTERN),
        datetime(2025, 11, 19, 16, 0, tzinfo=EASTERN),
    ]
