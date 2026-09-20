from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.contrib.messages import constants as message_levels
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Course, CourseMeeting, Semester, Student
from tickets.models import Ticket

SUBMIT = reverse("tickets:submit")
MY_QUESTIONS = reverse("tickets:ticket_list")


@pytest.mark.django_db
def test_submit_needs_a_student_in_the_current_semester(
    athe: AtheClient, semester: Semester, lucy: User
):
    athe.login(lucy)
    athe.get_redirects("/", SUBMIT)


@pytest.mark.django_db
def test_submit_offers_only_nearby_office_hours(
    athe: AtheClient,
    student: Student,
    office_hours: Course,
    make_course: Callable[..., Course],
    make_meeting: Callable[..., CourseMeeting],
    semester: Semester,
):
    soon = make_meeting(office_hours, days=3)
    make_meeting(office_hours, days=40)
    klass = make_course(semester, name="Intro to Olympiad")
    make_meeting(klass, days=3)

    athe.login("lucy")
    response = athe.get_ok(SUBMIT)

    field = response.context["form"].fields["meeting"]
    assert list(field.queryset) == [soon]
    assert not field.required


@pytest.mark.django_db
def test_submit_for_office_hours(
    athe: AtheClient, student: Student, sitting: CourseMeeting
):
    athe.login("lucy")
    athe.post_redirects(
        MY_QUESTIONS,
        SUBMIT,
        {"title": "FLT", "question": "How do I start?", "meeting": sitting.pk},
    )

    ticket = Ticket.objects.get()
    assert ticket.student == student
    assert ticket.meeting == sitting
    assert not ticket.is_resolved


@pytest.mark.django_db
def test_office_hours_submission_names_the_voice_channel(
    athe: AtheClient, student: Student, sitting: CourseMeeting
):
    athe.login("lucy")
    response = athe.post(
        SUBMIT,
        {"title": "FLT", "question": "How do I start?", "meeting": sitting.pk},
        follow=True,
    )

    (message,) = response.context["messages"]
    assert message.level == message_levels.SUCCESS
    assert "office-hours-voice-1" in str(message)
    assert sitting.course.name in str(message)


@pytest.mark.django_db
def test_submit_for_discord_dm(athe: AtheClient, student: Student):
    athe.login("lucy")
    athe.post_redirects(
        MY_QUESTIONS,
        SUBMIT,
        {
            "title": "What is a root of unity?",
            "question": "Just curious",
            "meeting": "",
        },
    )

    assert Ticket.objects.get().meeting is None


@pytest.mark.django_db
def test_my_questions_lists_newest_first(
    athe: AtheClient,
    student: Student,
    sitting: CourseMeeting,
    make_ticket: Callable[..., Ticket],
):
    make_ticket(student, title="First")
    make_ticket(student, title="Second", meeting=sitting)

    athe.login("lucy")
    response = athe.get_ok(MY_QUESTIONS)

    assert athe.texts_of(response, "ticket-title") == ["Second", "First"]
    assert athe.texts_of(response, "ticket-status") == ["Waiting", "Waiting"]


@pytest.mark.django_db
def test_my_questions_hides_other_students(
    athe: AtheClient,
    semester: Semester,
    student: Student,
    make_student: Callable[..., Student],
    make_ticket: Callable[..., Ticket],
):
    make_ticket(student, title="Mine")
    make_ticket(make_student(semester), title="Someone else's")

    athe.login("lucy")
    response = athe.get_ok(MY_QUESTIONS)

    assert athe.texts_of(response, "ticket-title") == ["Mine"]
    assert b"Someone else's" not in response.content


@pytest.mark.django_db
def test_resolved_questions_read_as_answered(
    athe: AtheClient,
    student: Student,
    staffer: User,
    make_ticket: Callable[..., Ticket],
):
    ticket = make_ticket(student)
    ticket.resolve(staffer)
    ticket.save()

    athe.login("lucy")
    response = athe.get_ok(MY_QUESTIONS)

    assert athe.text_of(response, "ticket-status") == "Answered"


@pytest.mark.django_db
def test_nav_offers_questions_to_everyone_but_review_only_to_staff(
    athe: AtheClient, student: Student, staffer: User
):
    athe.login("lucy")
    response = athe.get_ok("/")
    athe.assert_testid(response, "nav-tickets")
    athe.assert_no_testid(response, "nav-review-tickets")

    athe.login(staffer)
    response = athe.get_ok("/")
    athe.assert_testid(response, "nav-tickets", "nav-review-tickets")
