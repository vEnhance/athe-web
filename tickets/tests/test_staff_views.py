from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Course, CourseMeeting, Semester, Student
from home.models import StaffPhotoListing
from tickets.models import Ticket

REVIEW = reverse("tickets:review_list")


def make_ticket_for(student: Student, meeting: CourseMeeting) -> Ticket:
    return Ticket.objects.create(
        student=student, title=meeting.course.name, question="?", meeting=meeting
    )


def titles(athe: AtheClient, url: str) -> list[str]:
    return athe.texts_of(athe.get_ok(url), "ticket-title")


@pytest.mark.django_db
def test_review_list_is_staff_only(
    athe: AtheClient, student: Student, make_ticket: Callable[..., Ticket]
):
    ticket = make_ticket(student, title="FLT")

    athe.login("lucy")
    athe.get_redirects("/", REVIEW)
    athe.get_redirects("/", reverse("tickets:review_detail", kwargs={"pk": ticket.pk}))


@pytest.mark.django_db
def test_review_list_sorts_correctly(
    athe: AtheClient,
    student: Student,
    staffer: User,
    make_ticket: Callable[..., Ticket],
):
    # TODO rewrite this
    pass


@pytest.mark.django_db
def test_review_list_names_student_and_destination(
    athe: AtheClient,
    student: Student,
    staffer: User,
    sitting: CourseMeeting,
    make_ticket: Callable[..., Ticket],
):
    make_ticket(student, title="Office hours one", meeting=sitting)
    make_ticket(student, title="Discord one")

    athe.login(staffer)
    response = athe.get_ok(REVIEW)

    assert athe.texts_of(response, "ticket-student") == ["Lucy", "Lucy"]
    where = athe.texts_of(response, "ticket-where")
    assert where[0] == "Discord DM"
    assert where[1].startswith(sitting.course.name)


@pytest.mark.django_db
def test_review_list_flags_sessions_this_staffer_follows(
    athe: AtheClient,
    student: Student,
    staffer: User,
    semester: Semester,
    office_hours: Course,
    sitting: CourseMeeting,
    make_course: Callable[..., Course],
    make_meeting: Callable[..., CourseMeeting],
    make_staff_listing: Callable[..., StaffPhotoListing],
):
    other = make_course(
        semester,
        name="OH (Melody + Aaron)",
        is_club=True,
        is_office_hours=True,
    )
    office_hours.subscribed_staff.add(make_staff_listing(staffer))
    mine = make_ticket_for(student, sitting)
    make_ticket_for(student, make_meeting(other))

    athe.login(staffer)
    response = athe.get_ok(REVIEW)

    assert response.context["followed"] == {mine.pk}


@pytest.mark.django_db
def test_review_list_filters_by_session(
    athe: AtheClient,
    student: Student,
    staffer: User,
    semester: Semester,
    office_hours: Course,
    sitting: CourseMeeting,
    make_course: Callable[..., Course],
    make_meeting: Callable[..., CourseMeeting],
):
    other = make_course(
        semester,
        name="OH (Joshua + Tarun)",
        is_club=True,
        is_office_hours=True,
    )
    make_ticket_for(student, sitting)
    make_ticket_for(student, make_meeting(other))
    Ticket.objects.create(student=student, title="Discord one", question="?")

    athe.login(staffer)

    assert titles(athe, f"{REVIEW}?session={office_hours.pk}") == [office_hours.name]
    assert titles(athe, f"{REVIEW}?session=dm") == ["Discord one"]
    assert len(titles(athe, REVIEW)) == 3
    assert list(athe.get_ok(REVIEW).context["sessions"]) == [office_hours, other]


@pytest.mark.django_db
def test_staff_resolve_and_reopen(
    athe: AtheClient,
    student: Student,
    staffer: User,
    make_ticket: Callable[..., Ticket],
):
    ticket = make_ticket(student)
    url = reverse("tickets:review_detail", kwargs={"pk": ticket.pk})

    athe.login(staffer)
    athe.post_redirects(REVIEW, url, {"resolved": "on", "staff_notes": "Sent a hint."})

    ticket.refresh_from_db()
    assert ticket.is_resolved
    assert ticket.resolved_by == staffer
    assert ticket.staff_notes == "Sent a hint."

    athe.post_redirects(REVIEW, url, {"staff_notes": "Needs more work."})

    ticket.refresh_from_db()
    assert not ticket.is_resolved
    assert ticket.resolved_by is None


@pytest.mark.django_db
def test_editing_notes_keeps_who_resolved_it(
    athe: AtheClient,
    student: Student,
    staffer: User,
    make_user: Callable[..., User],
    make_ticket: Callable[..., Ticket],
):
    ticket = make_ticket(student)
    ticket.resolve(staffer)
    ticket.save()
    closed_at = ticket.resolved_at

    second = make_user(username="heather", is_staff=True)
    athe.login(second)
    athe.post_redirects(
        REVIEW,
        reverse("tickets:review_detail", kwargs={"pk": ticket.pk}),
        {"resolved": "on", "staff_notes": "Answered live."},
    )

    ticket.refresh_from_db()
    assert ticket.resolved_by == staffer
    assert ticket.resolved_at == closed_at
