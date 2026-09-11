from collections.abc import Callable
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student
from housepoints.models import Award

BULK_AWARD = reverse("housepoints:bulk_award")


@pytest.fixture
def staff(athe: AtheClient, make_user: Callable[..., User]) -> User:
    return athe.login(make_user(username="staff", is_staff=True))


@pytest.mark.django_db
def test_bulk_award_requires_staff(athe: AtheClient, make_user: Callable[..., User]):
    athe.login(make_user())
    assert athe.get(BULK_AWARD).status_code == 403


@pytest.mark.django_db
def test_bulk_award_staff_access(athe: AtheClient, semester: Semester, staff: User):
    response = athe.get_ok(BULK_AWARD)

    assert response.context["semester"] == semester
    assert response.context["results"] is None


@pytest.mark.django_db
def test_bulk_award_creates_awards(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
):
    alice = make_student(semester, house=Student.House.OWL, airtable_name="Alice Smith")
    bob = make_student(semester, house=Student.House.CAT, airtable_name="Bob Jones")

    response = athe.post_ok(
        BULK_AWARD,
        {
            "award_type": Award.AwardType.OFFICE_HOURS,
            "airtable_names": "Alice Smith\nBob Jones",
            "points": "",
            "description": "Week 1 OH",
        },
    )

    assert Award.objects.count() == 2
    alice_award = Award.objects.get(student=alice)
    assert alice_award.points == Award.DEFAULT_POINTS[Award.AwardType.OFFICE_HOURS]
    assert alice_award.house == Student.House.OWL
    assert alice_award.awarded_by == staff
    assert alice_award.description == "Week 1 OH"
    assert Award.objects.get(student=bob).house == Student.House.CAT
    athe.assert_testid(response, "bulk-award-awarded")


@pytest.mark.django_db
def test_bulk_award_custom_points(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
):
    student = make_student(semester, house=Student.House.BLOB, airtable_name="Alice")

    athe.post_ok(
        BULK_AWARD,
        {
            "award_type": Award.AwardType.CLASS_ATTENDANCE,
            "airtable_names": "Alice",
            "points": "3",
            "description": "Week 15 attendance",
        },
    )

    assert Award.objects.get(student=student).points == 3


@pytest.mark.django_db
def test_bulk_award_handles_missing_student(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
):
    """One unrecognised name is reported without costing the rest the award."""
    alice = make_student(semester, house=Student.House.OWL, airtable_name="Alice")

    response = athe.post_ok(
        BULK_AWARD,
        {
            "award_type": Award.AwardType.HOMEWORK,
            "airtable_names": "Alice\nNonexistent Student",
            "points": "",
            "description": "",
        },
    )

    assert list(Award.objects.values_list("student", flat=True)) == [alice.pk]
    results = response.context["results"]
    assert len(results.success) == 1
    assert len(results.errors) == 1
    athe.assert_testid(response, "bulk-award-awarded", "bulk-award-errors")


@pytest.mark.django_db
def test_bulk_award_handles_student_without_house(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
):
    make_student(semester, house="", airtable_name="Alice")

    response = athe.post_ok(
        BULK_AWARD,
        {
            "award_type": Award.AwardType.HOMEWORK,
            "airtable_names": "Alice",
            "points": "",
            "description": "",
        },
    )

    assert Award.objects.count() == 0
    assert len(response.context["results"].errors) == 1
    athe.assert_testid(response, "bulk-award-errors")


@pytest.mark.django_db
def test_bulk_award_no_current_semester(
    athe: AtheClient, staff: User, make_semester: Callable[..., Semester]
):
    """Bulk award has nowhere to put points with no current semester."""
    today = timezone.localdate()
    make_semester(
        name="Spring 2020",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=110),
    )

    athe.get_redirects(reverse("index"), BULK_AWARD)


@pytest.mark.django_db
def test_bulk_award_uses_a_semester_that_has_not_opened(
    athe: AtheClient, staff: User, make_semester: Callable[..., Semester]
):
    """Points can be set up against the semester being prepared: it is the
    current one whether or not its start date has arrived."""
    today = timezone.localdate()
    upcoming = make_semester(
        name="Fall 2026",
        start_date=today + timedelta(days=30),
        end_date=today + timedelta(days=140),
    )

    response = athe.get_ok(BULK_AWARD)

    assert response.context["semester"] == upcoming
