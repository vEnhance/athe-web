from collections.abc import Callable
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from courses.models import Course, CourseMeeting, Semester, Student
from tickets.models import Ticket


@pytest.mark.django_db
def test_office_hours_must_be_a_club(semester: Semester):
    klass = Course(
        semester=semester,
        name="Intro to Olympiad",
        description="Olympiad basics",
        is_office_hours=True,
    )
    with pytest.raises(ValidationError, match="Only a club"):
        klass.full_clean()
    with pytest.raises(IntegrityError):
        klass.save()


@pytest.mark.django_db
def test_office_hours_club_is_allowed(office_hours: Course):
    office_hours.description = "Weekly drop-in help"
    office_hours.full_clean()


@pytest.mark.django_db
def test_ticket_rejects_a_meeting_that_is_not_office_hours(
    semester: Semester,
    student: Student,
    make_course: Callable[..., Course],
    make_meeting: Callable[..., CourseMeeting],
):
    klass = make_course(semester, name="Intro to Olympiad")
    ticket = Ticket(student=student, title="A problem", question="?")
    ticket.meeting = make_meeting(klass)
    with pytest.raises(ValidationError):
        ticket.full_clean()


@pytest.mark.django_db
def test_office_hours_within_honours_the_horizon(
    office_hours: Course, make_meeting: Callable[..., CourseMeeting]
):
    soon = make_meeting(office_hours, days=3)
    make_meeting(office_hours, days=40)
    make_meeting(office_hours, days=-1)

    assert list(CourseMeeting.objects.office_hours_within(15)) == [soon]


@pytest.mark.django_db
def test_office_hours_within_skips_finished_semesters(
    make_semester: Callable[..., Semester],
    make_course: Callable[..., Course],
    make_meeting: Callable[..., CourseMeeting],
):
    today = timezone.localdate()
    over = make_semester(
        name="Spring 2025",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=1),
    )
    stale = make_course(over, name="OH (Old)", is_club=True, is_office_hours=True)
    make_meeting(stale, days=3)

    assert not CourseMeeting.objects.office_hours_within(15).exists()


@pytest.mark.django_db
def test_resolve_and_unresolve(
    student: Student, staffer, make_ticket: Callable[..., Ticket]
):
    ticket = make_ticket(student)
    assert not ticket.is_resolved

    ticket.resolve(staffer)
    ticket.save()
    ticket.refresh_from_db()
    assert ticket.is_resolved
    assert ticket.resolved_by == staffer

    ticket.unresolve()
    ticket.save()
    ticket.refresh_from_db()
    assert not ticket.is_resolved
    assert ticket.resolved_by is None
