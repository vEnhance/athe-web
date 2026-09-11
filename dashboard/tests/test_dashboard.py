from collections.abc import Callable
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.template.defaultfilters import date as date_filter
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Course, CourseMeeting, GlobalEvent, Semester, Student
from housepoints.models import Award
from reg import wizard
from reg.models import StudentInviteLink, StudentRegistration
from yearbook.models import YearbookEntry

INDEX = "/"


@pytest.fixture
def lucy(make_user: Callable[..., User]) -> User:
    return make_user(username="lucy", first_name="Lucy")


@pytest.fixture
def student(
    semester: Semester, lucy: User, make_student: Callable[..., Student]
) -> Student:
    return make_student(semester, user=lucy, house=Student.House.OWL)


@pytest.fixture
def next_semester(make_semester: Callable[..., Semester]) -> Semester:
    """A semester that has been set up but has not opened yet."""
    today = timezone.localdate()
    return make_semester(
        name="Spring 2026",
        slug="sp26",
        start_date=today + timedelta(days=30),
        end_date=today + timedelta(days=120),
        president_name="Greta",
    )


@pytest.fixture
def invite(semester: Semester) -> StudentInviteLink:
    return StudentInviteLink.objects.create(
        name="Fall 2025",
        semester=semester,
        expiration_date=timezone.now() + timedelta(days=30),
    )


def complete_registration(student: Student) -> StudentRegistration:
    """A registration with every questionnaire page saved."""
    return StudentRegistration.objects.create(
        student=student,
        completed_steps=[step.slug for step in wizard.STEPS],
    )


def listed(response: HttpResponse, key: str) -> list[str]:
    """The course names in one of the dashboard's two lists."""
    return [row.course.name for row in response.context[key]]


@pytest.mark.django_db
def test_root_shows_splash_when_logged_out(athe: AtheClient):
    """Anonymous visitors still get the public homepage at /."""
    response = athe.get_ok(INDEX)

    athe.assert_testid(response, "splash-hero")
    athe.assert_no_testid(response, "dash-greeting")


@pytest.mark.django_db
def test_root_shows_dashboard_when_logged_in(athe: AtheClient, student: Student):
    """Logged-in users get the dashboard at / instead of the splash page."""
    athe.login("lucy")
    response = athe.get_ok(INDEX)

    athe.assert_testid(response, "dash-greeting")
    athe.assert_no_testid(response, "splash-hero")
    assert athe.text_of(response, "dash-greeting") == "Hi, Lucy!"


@pytest.mark.django_db
def test_dashboard_lists_classes_and_clubs_with_next_meeting(
    athe: AtheClient,
    semester: Semester,
    student: Student,
    make_course: Callable[..., Course],
):
    """Enrolled classes and clubs are listed apart, each with its next meeting."""
    klass = make_course(semester, name="Intro to Olympiad")
    club = make_course(semester, name="Origami Club", is_club=True)
    klass.students.add(student)
    club.students.add(student)

    now = timezone.now()
    for days, title in ((-7, "Old lesson"), (1, "Next lesson"), (8, "Later lesson")):
        CourseMeeting.objects.create(
            course=klass, start_time=now + timedelta(days=days), title=title
        )

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert listed(response, "dash_classes") == ["Intro to Olympiad"]
    assert listed(response, "dash_clubs") == ["Origami Club"]
    (klass_row,) = response.context["dash_classes"]
    (club_row,) = response.context["dash_clubs"]
    assert klass_row.next_meeting.title == "Next lesson"
    assert club_row.next_meeting is None
    athe.assert_testid(response, "dash-course-unscheduled")


@pytest.mark.django_db
def test_dashboard_omits_courses_from_inactive_semesters(
    athe: AtheClient,
    student: Student,
    make_semester: Callable[..., Semester],
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    """Courses from a semester that has ended stay off the dashboard."""
    today = timezone.localdate()
    old_semester = make_semester(
        name="Spring 2025",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=100),
    )
    old_student = make_student(old_semester, user=student.user)
    old_course = make_course(old_semester, name="Ancient History of Numbers")
    old_course.students.add(old_student)

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert listed(response, "dash_classes") == []


@pytest.mark.django_db
def test_dashboard_house_squares(
    athe: AtheClient,
    semester: Semester,
    student: Student,
    make_student: Callable[..., Student],
):
    """The house squares show the house total and the student's own total."""
    housemate = make_student(semester, house=Student.House.OWL)
    for who in (student, housemate):
        Award.objects.create(
            semester=semester,
            student=who,
            award_type=Award.AwardType.HOMEWORK,
            points=5,
        )

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["house_display"] == "Owls"
    assert response.context["house_points"] == 10
    assert response.context["my_points"] == 5
    athe.assert_testid(response, "dash-house-square", "dash-my-points-square")

    # The house tile drills into this student's own house for the semester,
    # and house_detail turns non-members away, so check she can follow it.
    house_detail = reverse(
        "housepoints:house_detail",
        kwargs={"slug": semester.slug, "house": Student.House.OWL},
    )
    assert response.context["house_detail_url"] == house_detail
    athe.get_ok(house_detail)


@pytest.mark.django_db
def test_dashboard_prompts_for_missing_yearbook_entry(
    athe: AtheClient, semester: Semester, student: Student
):
    """Without an entry, the yearbook square names the semester and invites one."""
    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["yearbook_entry"] is None
    assert response.context["yearbook_student"] == student
    athe.assert_testid(response, "dash-yearbook-prompt", "dash-yearbook-create")
    assert "Fall 2025" in athe.text_of(response, "dash-yearbook-prompt")


@pytest.mark.django_db
def test_dashboard_previews_existing_yearbook_entry(
    athe: AtheClient, semester: Semester, student: Student
):
    """With an entry, the square previews it and links to the edit form."""
    entry = YearbookEntry.objects.create(
        student=student, display_name="Lucy L.", bio="I like combinatorics."
    )

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["yearbook_entry"] == entry
    # The dashboard shows the same card the yearbook listing does.
    athe.assert_testid(response, "yearbook-card", "dash-yearbook-edit")
    card = athe.text_of(response, "yearbook-card")
    assert "Lucy L." in card
    assert "I like combinatorics." in card
    assert response.context["yearbook_url"] == reverse(
        "yearbook:entry_list", kwargs={"slug": semester.slug}
    )


@pytest.mark.django_db
def test_dashboard_staff_section_is_staff_only(
    athe: AtheClient, make_user: Callable[..., User]
):
    """Staff tools only render for staff, and admin tools only for superusers."""
    make_user(username="pupil")
    make_user(username="teacher", is_staff=True)
    make_user(username="boss", is_staff=True, is_superuser=True)

    athe.login("pupil")
    athe.assert_no_testid(athe.get_ok(INDEX), "dash-staff-links", "dash-admin-links")

    athe.login("teacher")
    response = athe.get_ok(INDEX)
    athe.assert_testid(response, "dash-staff-links")
    athe.assert_no_testid(response, "dash-admin-links")

    athe.login("boss")
    athe.assert_testid(athe.get_ok(INDEX), "dash-staff-links", "dash-admin-links")


@pytest.mark.django_db
def test_dashboard_works_for_staff_without_student_record(
    athe: AtheClient, make_user: Callable[..., User]
):
    """Staff have no Student row, so they get the generic house/yearbook squares."""
    make_user(username="teacher", is_staff=True)

    athe.login("teacher")
    response = athe.get_ok(INDEX)

    assert response.context["house_url"] == reverse("housepoints:leaderboard")
    assert response.context["yearbook_url"] == reverse("yearbook:index")
    athe.assert_no_testid(response, "dash-house-tiles", "yearbook-card")


@pytest.mark.django_db
def test_navbar_dropdown_is_trimmed(athe: AtheClient, student: Student):
    """The user dropdown keeps the dashboard, blog and account entries only.

    Everything else moved onto the dashboard itself, so this compares the whole
    menu rather than hunting for the entries that were dropped.
    """
    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert athe.testids(response, "nav-") == [
        "nav-dashboard",
        "nav-calendar",
        "nav-upcoming",
        "nav-blog",
        "nav-profile",
        "nav-providers",
        "nav-logout",
    ]


@pytest.mark.django_db
def test_section_headings_carry_a_badge_to_the_full_page(
    athe: AtheClient, semester: Semester, student: Student
):
    """Each heading is plain text; the badge beside it is what links onward."""
    athe.login("lucy")
    response = athe.get_ok(INDEX)

    athe.assert_testid(
        response,
        "dash-see-all-classes",
        "dash-see-all-clubs",
        "dash-see-all-house",
        "dash-see-all-yearbook",
    )
    assert response.context["house_url"] == reverse(
        "housepoints:leaderboard_semester", kwargs={"slug": semester.slug}
    )
    assert response.context["yearbook_url"] == reverse(
        "yearbook:entry_list", kwargs={"slug": semester.slug}
    )


@pytest.mark.django_db
def test_dashboard_summarises_global_events(
    athe: AtheClient, semester: Semester, student: Student
):
    """The intro paragraph counts the semester's events and names the next one."""
    now = timezone.now()
    GlobalEvent.objects.create(
        semester=semester, title="Opening Social", start_time=now - timedelta(days=3)
    )
    soonest = GlobalEvent.objects.create(
        semester=semester, title="Guest Lecture", start_time=now + timedelta(days=2)
    )
    GlobalEvent.objects.create(
        semester=semester, title="Closing Party", start_time=now + timedelta(days=40)
    )

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    # The count covers the whole semester; "next" looks only forwards.
    assert response.context["global_event_count"] == 3
    assert response.context["next_global_event"] == soonest
    assert "Closing Party" not in athe.text_of(response, "dash-global-events")


@pytest.mark.django_db
def test_dashboard_global_events_all_in_the_past(
    athe: AtheClient, semester: Semester, student: Student
):
    """With nothing left to come, there is a count but no next event."""
    GlobalEvent.objects.create(
        semester=semester,
        title="Opening Social",
        start_time=timezone.now() - timedelta(days=3),
    )

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["global_event_count"] == 1
    assert response.context["next_global_event"] is None


@pytest.mark.django_db
def test_dashboard_says_nothing_without_global_events(
    athe: AtheClient, semester: Semester, student: Student
):
    """No events at all means no sentence about them."""
    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["global_event_count"] == 0
    assert athe.text_of(response, "dash-global-events") == ""


@pytest.mark.django_db
def test_dashboard_ignores_events_from_other_semesters(
    athe: AtheClient,
    student: Student,
    make_semester: Callable[..., Semester],
    make_student: Callable[..., Student],
):
    """ "This semester" excludes a semester the student is no longer in."""
    today = timezone.localdate()
    old_semester = make_semester(
        name="Spring 2025",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=100),
    )
    make_student(old_semester, user=student.user)
    GlobalEvent.objects.create(
        semester=old_semester,
        title="Last Year's Picnic",
        start_time=timezone.now() - timedelta(days=150),
    )

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["global_event_count"] == 0


@pytest.mark.django_db
def test_notice_links_an_unfinished_registration(
    athe: AtheClient, semester: Semester, student: Student, invite: StudentInviteLink
):
    """A half-filled questionnaire is the first thing the dashboard asks for."""
    StudentRegistration.objects.create(
        student=student, completed_steps=[wizard.FIRST_STEP.slug]
    )

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    notice = response.context["notice"]
    assert notice.kind == "registration"
    assert notice.semester == semester
    assert notice.url == invite.get_absolute_url()


@pytest.mark.django_db
def test_notice_skips_registration_without_a_live_invite_link(
    athe: AtheClient, semester: Semester, student: Student
):
    """The questionnaire only opens off an invite link, so an expired one has
    nothing to offer and the banner stays away."""
    StudentInviteLink.objects.create(
        name="Fall 2025",
        semester=semester,
        expiration_date=timezone.now() - timedelta(days=1),
    )
    StudentRegistration.objects.create(student=student, completed_steps=[])

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["notice"] is None
    athe.assert_no_testid(response, "dash-notice")


@pytest.mark.django_db
def test_notice_explains_pending_assignments(
    athe: AtheClient,
    next_semester: Semester,
    lucy: User,
    make_student: Callable[..., Student],
):
    """Registered, semester not open, no classes yet: the matching is pending."""
    complete_registration(make_student(next_semester, user=lucy))

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["notice"].kind == "assignments"
    assert "Greta" in athe.text_of(response, "dash-notice")


@pytest.mark.django_db
def test_notice_omits_the_president_when_the_semester_has_no_name_for_one(
    athe: AtheClient,
    next_semester: Semester,
    lucy: User,
    make_student: Callable[..., Student],
):
    """Without a president_name the same message drops the name rather than
    leaving a gap in the sentence."""
    next_semester.president_name = ""
    next_semester.save()
    complete_registration(make_student(next_semester, user=lucy))

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["notice"].kind == "assignments"
    assert "Greta" not in athe.text_of(response, "dash-notice")


@pytest.mark.django_db
def test_notice_goes_away_once_classes_are_assigned(
    athe: AtheClient,
    next_semester: Semester,
    lucy: User,
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    """A class on the books means the matching has run for this student."""
    student = make_student(next_semester, user=lucy)
    complete_registration(student)
    make_course(next_semester).students.add(student)

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["notice"] is None


@pytest.mark.django_db
def test_notice_ignores_clubs_when_looking_for_assignments(
    athe: AtheClient,
    next_semester: Semester,
    lucy: User,
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    """Clubs are joined, not assigned, so one does not answer the question."""
    student = make_student(next_semester, user=lucy)
    complete_registration(student)
    make_course(next_semester, name="Origami Club", is_club=True).students.add(student)

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["notice"].kind == "assignments"


@pytest.mark.django_db
def test_notice_stops_once_the_semester_has_started(
    athe: AtheClient, semester: Semester, student: Student
):
    """Once classes are running, the empty course list speaks for itself."""
    complete_registration(student)

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["notice"] is None
    athe.assert_testid(response, "dash-no-classes")


@pytest.mark.django_db
def test_notice_points_an_unenrolled_user_at_the_current_semester(
    athe: AtheClient, semester: Semester, make_user: Callable[..., User]
):
    """Someone with no Student row at all is told which session they missed."""
    semester.president_name = "Greta"
    semester.save()
    make_user(username="stranger")

    athe.login("stranger")
    response = athe.get_ok(INDEX)

    notice = response.context["notice"]
    assert notice.kind == "not_enrolled"
    assert notice.semester == semester
    assert "Greta" in athe.text_of(response, "dash-notice")


@pytest.mark.django_db
def test_notice_hides_semesters_the_user_may_not_see(
    athe: AtheClient, semester: Semester, make_user: Callable[..., User]
):
    """An invisible semester is not one to send an unenrolled student after."""
    semester.visible = False
    semester.save()
    make_user(username="stranger")

    athe.login("stranger")
    response = athe.get_ok(INDEX)

    assert response.context["notice"] is None


@pytest.mark.django_db
def test_notice_spares_staff_the_enrolment_messages(
    athe: AtheClient, semester: Semester, make_user: Callable[..., User]
):
    """Staff have no Student row by design, so that is not news to report."""
    make_user(username="teacher", is_staff=True)

    athe.login("teacher")
    response = athe.get_ok(INDEX)

    assert response.context["notice"] is None
    athe.assert_no_testid(response, "dash-notice")


@pytest.mark.django_db
def test_start_date_is_stated_to_staff_too(
    athe: AtheClient,
    next_semester: Semester,
    make_user: Callable[..., User],
    make_course: Callable[..., Course],
    make_staff_listing,
):
    """Staff get the start date too, alongside the class they are preparing."""
    teacher = make_user(username="teacher", is_staff=True)
    course = make_course(next_semester, instructor=make_staff_listing(teacher))

    athe.login("teacher")
    response = athe.get_ok(INDEX)

    assert response.context["upcoming_semester"] == next_semester
    assert listed(response, "dash_classes") == [course.name]


@pytest.mark.django_db
def test_notice_prefers_the_semester_with_something_outstanding(
    athe: AtheClient,
    semester: Semester,
    student: Student,
    next_semester: Semester,
    make_student: Callable[..., Student],
):
    """A settled current semester does not hide next semester's paperwork."""
    complete_registration(student)
    StudentInviteLink.objects.create(
        name="Spring 2026",
        semester=next_semester,
        expiration_date=timezone.now() + timedelta(days=60),
    )
    StudentRegistration.objects.create(
        student=make_student(next_semester, user=student.user), completed_steps=[]
    )

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    notice = response.context["notice"]
    assert notice.kind == "registration"
    assert notice.semester == next_semester


@pytest.mark.django_db
def test_start_date_is_stated_before_the_semester_opens(
    athe: AtheClient, next_semester: Semester, make_user: Callable[..., User]
):
    """The start date is a fact about the current semester, printed alongside
    whatever else the page has to say rather than instead of it."""
    make_user(username="stranger")

    athe.login("stranger")
    response = athe.get_ok(INDEX)

    assert response.context["upcoming_semester"] == next_semester
    start = date_filter(next_semester.start_date, "F j, Y")
    assert start in athe.text_of(response, "dash-upcoming-semester")
    # A semester that has not opened is still the current one, so the banner
    # about not being enrolled in it is accurate and no longer suppressed.
    assert response.context["notice"].kind == "not_enrolled"


@pytest.mark.django_db
def test_start_date_is_stated_to_a_fully_sorted_student(
    athe: AtheClient,
    next_semester: Semester,
    lucy: User,
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    """A student with nothing outstanding still gets told when it all begins."""
    student = make_student(next_semester, user=lucy)
    complete_registration(student)
    make_course(next_semester).students.add(student)

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["upcoming_semester"] == next_semester


@pytest.mark.django_db
def test_notice_stays_quiet_while_a_semester_is_running(
    athe: AtheClient, semester: Semester, student: Student, next_semester: Semester
):
    """A semester already underway is not something to announce."""
    complete_registration(student)

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["upcoming_semester"] is None
    athe.assert_no_testid(response, "dash-upcoming-semester")


@pytest.mark.django_db
def test_yearbook_keeps_showing_an_alumna_her_last_entry(
    athe: AtheClient,
    make_user: Callable[..., User],
    make_semester: Callable[..., Semester],
    make_student: Callable[..., Student],
):
    """A student whose only semester has ended still reaches her own entry."""
    today = timezone.localdate()
    old_semester = make_semester(
        name="Spring 2025",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=100),
    )
    old_student = make_student(old_semester, user=make_user(username="alum"))
    entry = YearbookEntry.objects.create(
        student=old_student, display_name="Alum A.", bio="I liked combinatorics."
    )

    athe.login("alum")
    response = athe.get_ok(INDEX)

    assert response.context["yearbook_entry"] == entry
    assert response.context["yearbook_open"] is False
    assert response.context["yearbook_url"] == reverse(
        "yearbook:entry_list", kwargs={"slug": old_semester.slug}
    )
    athe.assert_testid(response, "yearbook-card")
    athe.assert_no_testid(response, "dash-yearbook-edit")


@pytest.mark.django_db
def test_yearbook_says_an_ended_semester_is_closed(
    athe: AtheClient,
    make_user: Callable[..., User],
    make_semester: Callable[..., Semester],
    make_student: Callable[..., Student],
):
    """An alumna with no entry is told the window has shut, not invited to add."""
    today = timezone.localdate()
    old_semester = make_semester(
        name="Spring 2025",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=100),
    )
    make_student(old_semester, user=make_user(username="alum"))

    athe.login("alum")
    response = athe.get_ok(INDEX)

    athe.assert_testid(response, "dash-yearbook-closed")
    athe.assert_no_testid(response, "dash-yearbook-create")
    assert "Spring 2025" in athe.text_of(response, "dash-yearbook-closed")


@pytest.mark.django_db
def test_yearbook_opens_before_the_semester_starts(
    athe: AtheClient,
    next_semester: Semester,
    lucy: User,
    make_student: Callable[..., Student],
):
    """An incoming student can write her entry ahead of the semester opening."""
    student = make_student(next_semester, user=lucy)

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["yearbook_open"] is True
    athe.assert_testid(response, "dash-yearbook-create")
    assert "Spring 2026" in athe.text_of(response, "dash-yearbook-prompt")
    # The button has to actually go somewhere she is allowed.
    athe.get_ok(reverse("yearbook:create", kwargs={"student_pk": student.pk}))


@pytest.mark.django_db
def test_yearbook_follows_the_most_recent_semester(
    athe: AtheClient,
    semester: Semester,
    student: Student,
    next_semester: Semester,
    make_student: Callable[..., Student],
):
    """With rows in two semesters, the yearbook square tracks the later one."""
    later = make_student(next_semester, user=student.user)
    YearbookEntry.objects.create(
        student=student, display_name="Old Lucy", bio="Last semester."
    )

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    # The Fall 2025 entry belongs to the older row, so it is not the one shown.
    assert response.context["yearbook_student"] == later
    assert response.context["yearbook_entry"] is None
    assert response.context["yearbook_url"] == reverse(
        "yearbook:entry_list", kwargs={"slug": next_semester.slug}
    )
    assert "Spring 2026" in athe.text_of(response, "dash-yearbook-prompt")


@pytest.mark.django_db
def test_empty_sections_say_so_when_no_semester_is_left(
    athe: AtheClient,
    make_user: Callable[..., User],
    make_semester: Callable[..., Semester],
):
    """Only a site with nothing unfinished on the books has no semester for
    these sections to be about."""
    today = timezone.localdate()
    make_semester(
        name="Spring 2025",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=100),
    )
    make_user(username="stranger")

    athe.login("stranger")
    response = athe.get_ok(INDEX)

    assert response.context["has_current_semester"] is False
    athe.assert_testid(response, "dash-house-no-semester", "dash-yearbook-no-semester")
    assert response.context["house_url"] == reverse("housepoints:leaderboard")
    assert response.context["yearbook_url"] == reverse("yearbook:index")


@pytest.mark.django_db
def test_empty_sections_speak_of_a_semester_yet_to_open(
    athe: AtheClient, next_semester: Semester, make_user: Callable[..., User]
):
    """A semester waiting to start is still one to talk about, so these keep
    their ordinary wording rather than claiming there is nothing."""
    make_user(username="stranger")

    athe.login("stranger")
    response = athe.get_ok(INDEX)

    assert response.context["has_current_semester"] is True
    athe.assert_testid(response, "dash-house-unassigned")
    athe.assert_no_testid(
        response, "dash-house-no-semester", "dash-yearbook-no-semester"
    )


@pytest.mark.django_db
def test_empty_sections_keep_their_wording_mid_semester(
    athe: AtheClient, semester: Semester, student: Student
):
    """With a semester underway, the sections still speak about it."""
    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert response.context["has_current_semester"] is True
    athe.assert_testid(response, "dash-no-classes", "dash-no-clubs")
    athe.assert_no_testid(
        response, "dash-house-no-semester", "dash-yearbook-no-semester"
    )


@pytest.mark.django_db
def test_dashboard_lists_courses_from_a_semester_about_to_open(
    athe: AtheClient,
    next_semester: Semester,
    lucy: User,
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    """A class is on the dashboard as soon as it exists, so a student enrolled
    ahead of the semester can find it instead of staring at an empty list."""
    student = make_student(next_semester, user=lucy)
    complete_registration(student)
    klass = make_course(next_semester, name="Intro to Olympiad")
    club = make_course(next_semester, name="Origami Club", is_club=True)
    klass.students.add(student)
    club.students.add(student)
    first = CourseMeeting.objects.create(
        course=klass,
        start_time=timezone.now() + timedelta(days=31),
        title="First lesson",
    )

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    assert listed(response, "dash_classes") == ["Intro to Olympiad"]
    assert listed(response, "dash_clubs") == ["Origami Club"]
    assert response.context["dash_classes"][0].next_meeting == first
    assert response.context["upcoming_semester"] == next_semester


@pytest.mark.django_db
def test_dashboard_lists_courses_an_instructor_is_preparing(
    athe: AtheClient,
    next_semester: Semester,
    make_user: Callable[..., User],
    make_course: Callable[..., Course],
    make_staff_listing,
):
    """Same for a class someone teaches, which is the point of showing it early."""
    teacher = make_user(username="teacher", is_staff=True)
    make_course(
        next_semester, name="Intro to Olympiad", instructor=make_staff_listing(teacher)
    )

    athe.login("teacher")
    response = athe.get_ok(INDEX)

    assert listed(response, "dash_classes") == ["Intro to Olympiad"]


@pytest.mark.django_db
def test_dashboard_orders_a_coming_semester_after_the_running_one(
    athe: AtheClient,
    semester: Semester,
    student: Student,
    next_semester: Semester,
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    """Enrolled either side of the turn, the class in progress comes first."""
    make_course(semester, name="Zebra Theory").students.add(student)
    later = make_student(next_semester, user=student.user)
    make_course(next_semester, name="Aardvark Theory").students.add(later)

    athe.login("lucy")
    response = athe.get_ok(INDEX)

    # Alphabetically Aardvark would win; the running semester outranks it.
    assert listed(response, "dash_classes") == ["Zebra Theory", "Aardvark Theory"]
