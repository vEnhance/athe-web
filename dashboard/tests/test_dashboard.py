import re
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.template.defaultfilters import date as date_filter
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseMeeting, GlobalEvent, Semester, Student
from housepoints.models import Award
from reg import wizard
from reg.models import StudentInviteLink, StudentRegistration
from yearbook.models import YearbookEntry


@pytest.fixture
def semester() -> Semester:
    today = timezone.localdate()
    return Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=80),
    )


@pytest.fixture
def student(semester: Semester) -> Student:
    user = User.objects.create_user(
        username="lucy", password="password", first_name="Lucy"
    )
    return Student.objects.create(
        user=user,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Lucy",
    )


def visible_text(content: str) -> str:
    """The page with its markup stripped, so tests can assert on what is shown."""
    return " ".join(re.sub(r"<[^>]+>", " ", content).split())


@pytest.fixture
def client_for():
    def _login(username: str) -> Client:
        client = Client()
        client.login(username=username, password="password")
        return client

    return _login


@pytest.mark.django_db
def test_root_shows_splash_when_logged_out():
    """Anonymous visitors still get the public homepage at /."""
    response = Client().get(reverse("index"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Bringing extraordinary young women together" in content
    assert "Hi," not in content


@pytest.mark.django_db
def test_root_shows_dashboard_when_logged_in(student: Student, client_for):
    """Logged-in users get the dashboard at / instead of the splash page."""
    response = client_for("lucy").get(reverse("index"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Hi, Lucy" in content
    assert "Bringing extraordinary young women together" not in content


@pytest.mark.django_db
def test_dashboard_lists_classes_and_clubs_with_next_meeting(
    semester: Semester, student: Student, client_for
):
    """Enrolled classes and clubs are listed apart, each with its next meeting."""
    klass = Course.objects.create(
        name="Intro to Olympiad", description="", semester=semester
    )
    club = Course.objects.create(
        name="Origami Club", description="", semester=semester, is_club=True
    )
    klass.students.add(student)
    club.students.add(student)

    now = timezone.now()
    CourseMeeting.objects.create(
        course=klass, start_time=now - timedelta(days=7), title="Old lesson"
    )
    CourseMeeting.objects.create(
        course=klass, start_time=now + timedelta(days=1), title="Next lesson"
    )
    CourseMeeting.objects.create(
        course=klass, start_time=now + timedelta(days=8), title="Later lesson"
    )

    content = client_for("lucy").get(reverse("index")).content.decode()

    assert "Intro to Olympiad" in content
    assert "Origami Club" in content
    # Only the soonest upcoming meeting is shown for the class.
    assert "Next lesson" in content
    assert "Old lesson" not in content
    assert "Later lesson" not in content
    # The club has no meetings scheduled at all.
    assert "No meetings scheduled" in content


@pytest.mark.django_db
def test_dashboard_omits_courses_from_inactive_semesters(
    semester: Semester, student: Student, client_for
):
    """Courses from a semester that has ended stay off the dashboard."""
    old_semester = Semester.objects.create(
        name="Spring 2025",
        slug="sp25",
        start_date=timezone.localdate() - timedelta(days=200),
        end_date=timezone.localdate() - timedelta(days=100),
    )
    old_student = Student.objects.create(
        user=student.user, semester=old_semester, airtable_name="Lucy"
    )
    old_course = Course.objects.create(
        name="Ancient History of Numbers", description="", semester=old_semester
    )
    old_course.students.add(old_student)

    content = client_for("lucy").get(reverse("index")).content.decode()

    assert "Ancient History of Numbers" not in content


@pytest.mark.django_db
def test_dashboard_house_squares(semester: Semester, student: Student, client_for):
    """The house squares show the house total and the student's own total."""
    housemate = Student.objects.create(
        semester=semester, house=Student.House.OWL, airtable_name="Housemate"
    )
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=housemate,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )

    client = client_for("lucy")
    content = client.get(reverse("index")).content.decode()

    # Each tile is just its label and its number.
    assert "Owls 10" in visible_text(content)
    assert "Your Points 5" in visible_text(content)
    # The house tile drills into this student's own house for the semester,
    # while the section badge stops at the semester's leaderboard.
    house_detail = reverse(
        "housepoints:house_detail",
        kwargs={"slug": semester.slug, "house": Student.House.OWL},
    )
    assert f'href="{house_detail}"' in content
    # house_detail turns non-members away, so check the student can follow it.
    assert client.get(house_detail).status_code == 200
    assert reverse("housepoints:my_awards") in content


@pytest.mark.django_db
def test_dashboard_prompts_for_missing_yearbook_entry(
    semester: Semester, student: Student, client_for
):
    """Without an entry, the yearbook square names the semester and invites one."""
    content = client_for("lucy").get(reverse("index")).content.decode()

    text = visible_text(content)
    assert "You don't have an entry yet for Fall 2025." in text
    assert "Add entry" in text
    assert reverse("yearbook:create", kwargs={"student_pk": student.pk}) in content


@pytest.mark.django_db
def test_dashboard_previews_existing_yearbook_entry(
    semester: Semester, student: Student, client_for
):
    """With an entry, the square previews it and links to the edit form."""
    entry = YearbookEntry.objects.create(
        student=student, display_name="Lucy L.", bio="I like combinatorics."
    )

    content = client_for("lucy").get(reverse("index")).content.decode()

    # The dashboard shows the same card the yearbook listing does.
    assert "Lucy L." in content
    assert "I like combinatorics." in content
    assert "yearbook-card" in content
    assert reverse("yearbook:edit", kwargs={"pk": entry.pk}) in content
    # The section heading links into the semester's yearbook.
    assert reverse("yearbook:entry_list", kwargs={"slug": semester.slug}) in content


@pytest.mark.django_db
def test_dashboard_staff_section_is_staff_only(client_for):
    """Staff tools only render for staff, and admin tools only for superusers."""
    User.objects.create_user(username="pupil", password="password")
    User.objects.create_user(username="teacher", password="password", is_staff=True)
    User.objects.create_user(
        username="boss", password="password", is_staff=True, is_superuser=True
    )

    pupil = client_for("pupil").get(reverse("index")).content.decode()
    assert "TA Sign-in Sheet" not in pupil
    assert "Bulk Create Students" not in pupil

    teacher = client_for("teacher").get(reverse("index")).content.decode()
    assert "TA Sign-in Sheet" in teacher
    assert reverse("courses:staff_schedule") in teacher
    assert "Bulk Create Students" not in teacher

    boss = client_for("boss").get(reverse("index")).content.decode()
    assert "TA Sign-in Sheet" in boss
    assert "Bulk Create Students" in boss
    assert reverse("reg:upload-assignments") in boss
    assert reverse("admin:index") in boss


@pytest.mark.django_db
def test_dashboard_works_for_staff_without_student_record(client_for):
    """Staff have no Student row, so they get the generic house/yearbook squares."""
    User.objects.create_user(username="teacher", password="password", is_staff=True)

    response = client_for("teacher").get(reverse("index"))
    content = response.content.decode()

    assert response.status_code == 200
    # Just the headings and their badges, with no placeholder tiles or card.
    assert reverse("housepoints:leaderboard") in content
    assert reverse("yearbook:index") in content
    assert "dash-square" not in content
    assert "yearbook-card" not in content


@pytest.mark.django_db
def test_navbar_dropdown_is_trimmed(student: Student, client_for):
    """The user dropdown keeps the dashboard, blog and account entries only."""
    content = client_for("lucy").get(reverse("index")).content.decode()

    assert '<a class="dropdown-item" href="/">Dashboard</a>' in content
    assert "My Blog Posts" in content
    assert "Profile Settings" in content
    assert "Login Providers" in content
    # Moved onto the dashboard itself.
    assert "House Standings" not in content
    assert "Clubs and Events" not in content


@pytest.mark.django_db
def test_section_headings_carry_a_badge_to_the_full_page(
    semester: Semester, student: Student, client_for
):
    """Each heading is plain text; the badge beside it is what links onward."""
    content = client_for("lucy").get(reverse("index")).content.decode()
    text = visible_text(content)

    assert "Classes See all" in text
    assert "Clubs See all" in text
    assert "House Points See all" in text
    assert "Yearbook See all" in text
    for url in (
        reverse("courses:my_courses"),
        reverse("courses:my_clubs"),
        reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug}),
        reverse("yearbook:entry_list", kwargs={"slug": semester.slug}),
    ):
        assert f'href="{url}">' in content


@pytest.mark.django_db
def test_dashboard_summarises_global_events(
    semester: Semester, student: Student, client_for
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

    content = client_for("lucy").get(reverse("index")).content.decode()
    text = visible_text(content)

    # The count covers the whole semester; "next" looks only forwards.
    assert "There are 3 global events this semester" in text
    assert "The next one is Guest Lecture at" in text
    assert "Closing Party" not in text
    assert reverse("courses:global_events") in content
    assert soonest.get_absolute_url() in content


@pytest.mark.django_db
def test_dashboard_global_events_all_in_the_past(
    semester: Semester, student: Student, client_for
):
    """With nothing left to come, the second sentence says so."""
    GlobalEvent.objects.create(
        semester=semester,
        title="Opening Social",
        start_time=timezone.now() - timedelta(days=3),
    )

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "There was 1 global event this semester" in text
    assert "There are no future global events scheduled." in text


@pytest.mark.django_db
def test_dashboard_says_nothing_without_global_events(
    semester: Semester, student: Student, client_for
):
    """No events at all means no sentence about them."""
    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "global event" not in text


@pytest.mark.django_db
def test_dashboard_ignores_events_from_other_semesters(
    semester: Semester, student: Student, client_for
):
    """ "This semester" excludes a semester the student is no longer in."""
    old_semester = Semester.objects.create(
        name="Spring 2025",
        slug="sp25",
        start_date=timezone.localdate() - timedelta(days=200),
        end_date=timezone.localdate() - timedelta(days=100),
    )
    Student.objects.create(
        user=student.user, semester=old_semester, airtable_name="Lucy"
    )
    GlobalEvent.objects.create(
        semester=old_semester,
        title="Last Year's Picnic",
        start_time=timezone.now() - timedelta(days=150),
    )

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "global event" not in text
    assert "Last Year's Picnic" not in text


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


@pytest.fixture
def next_semester() -> Semester:
    """A semester that has been set up but has not opened yet."""
    today = timezone.localdate()
    return Semester.objects.create(
        name="Spring 2026",
        slug="sp26",
        start_date=today + timedelta(days=30),
        end_date=today + timedelta(days=120),
        president_name="Greta",
    )


@pytest.mark.django_db
def test_notice_links_an_unfinished_registration(
    student: Student, invite: StudentInviteLink, client_for
):
    """A half-filled questionnaire is the first thing the dashboard asks for."""
    StudentRegistration.objects.create(
        student=student, completed_steps=[wizard.FIRST_STEP.slug]
    )

    content = client_for("lucy").get(reverse("index")).content.decode()

    assert "Your registration for Fall 2025 isn't done yet" in visible_text(content)
    assert invite.get_absolute_url() in content


@pytest.mark.django_db
def test_notice_skips_registration_without_a_live_invite_link(
    semester: Semester, student: Student, client_for
):
    """The questionnaire only opens off an invite link, so an expired one has
    nothing to offer and the banner stays away."""
    StudentInviteLink.objects.create(
        name="Fall 2025",
        semester=semester,
        expiration_date=timezone.now() - timedelta(days=1),
    )
    StudentRegistration.objects.create(student=student, completed_steps=[])

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "isn't done yet" not in text


@pytest.mark.django_db
def test_notice_explains_pending_assignments(next_semester: Semester, client_for):
    """Registered, semester not open, no classes yet: the matching is pending."""
    user = User.objects.create_user(
        username="lucy", password="password", first_name="Lucy"
    )
    student = Student.objects.create(
        user=user, semester=next_semester, airtable_name="Lucy"
    )
    complete_registration(student)

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "Our glorious queen Greta is still working on course and house" in text
    assert "You'll get an email once that's done." in text


@pytest.mark.django_db
def test_notice_omits_the_president_when_the_semester_has_no_name_for_one(
    next_semester: Semester, client_for
):
    """Without a president_name the same message drops the name rather than
    leaving a gap in the sentence."""
    next_semester.president_name = ""
    next_semester.save()
    user = User.objects.create_user(username="lucy", password="password")
    complete_registration(
        Student.objects.create(user=user, semester=next_semester, airtable_name="Lucy")
    )

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "We're still working on course and house assignments!" in text
    assert "glorious queen" not in text


@pytest.mark.django_db
def test_notice_goes_away_once_classes_are_assigned(
    next_semester: Semester, client_for
):
    """A class on the books means the matching has run for this student."""
    user = User.objects.create_user(username="lucy", password="password")
    student = Student.objects.create(
        user=user, semester=next_semester, airtable_name="Lucy"
    )
    complete_registration(student)
    course = Course.objects.create(
        name="Intro to Olympiad", description="", semester=next_semester
    )
    course.students.add(student)

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "glorious queen" not in text


@pytest.mark.django_db
def test_notice_ignores_clubs_when_looking_for_assignments(
    next_semester: Semester, client_for
):
    """Clubs are joined, not assigned, so one does not answer the question."""
    user = User.objects.create_user(username="lucy", password="password")
    student = Student.objects.create(
        user=user, semester=next_semester, airtable_name="Lucy"
    )
    complete_registration(student)
    club = Course.objects.create(
        name="Origami Club", description="", semester=next_semester, is_club=True
    )
    club.students.add(student)

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "Our glorious queen Greta is still working" in text


@pytest.mark.django_db
def test_notice_stops_once_the_semester_has_started(
    semester: Semester, student: Student, client_for
):
    """Once classes are running, the empty course list speaks for itself."""
    complete_registration(student)

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "glorious queen" not in text
    assert "You are not enrolled in any classes this semester yet." in text


@pytest.mark.django_db
def test_notice_points_an_unenrolled_user_at_the_current_semester(
    semester: Semester, client_for
):
    """Someone with no Student row at all is told which session they missed."""
    semester.president_name = "Greta"
    semester.save()
    User.objects.create_user(username="stranger", password="password")

    text = visible_text(client_for("stranger").get(reverse("index")).content.decode())

    assert "You don't seem to be enrolled in the current session, Fall 2025." in text
    assert (
        "please look for the registration link from Greta to register, "
        "or contact Greta for details." in text
    )


@pytest.mark.django_db
def test_notice_hides_semesters_the_user_may_not_see(semester: Semester, client_for):
    """An invisible semester is not one to send an unenrolled student after."""
    semester.visible = False
    semester.save()
    User.objects.create_user(username="stranger", password="password")

    text = visible_text(client_for("stranger").get(reverse("index")).content.decode())

    assert "You don't seem to be enrolled" not in text


@pytest.mark.django_db
def test_notice_spares_staff_the_enrolment_messages(semester: Semester, client_for):
    """Staff have no Student row by design, so that is not news to report."""
    User.objects.create_user(username="teacher", password="password", is_staff=True)

    text = visible_text(client_for("teacher").get(reverse("index")).content.decode())

    assert "You don't seem to be enrolled" not in text
    assert "registration" not in text.lower()


@pytest.mark.django_db
def test_notice_warns_staff_that_the_semester_has_not_opened(
    next_semester: Semester, client_for
):
    """A course an instructor is about to teach is as invisible as a student's,
    since the class lists only carry the running semester either way."""
    teacher = User.objects.create_user(
        username="teacher", password="password", is_staff=True
    )
    course = Course.objects.create(
        name="Intro to Olympiad", description="", semester=next_semester
    )
    course.leaders.add(teacher)

    content = client_for("teacher").get(reverse("index")).content.decode()
    text = visible_text(content)

    assert "The session Spring 2026 hasn't started yet!" in text
    # Which is the point: the class they lead is nowhere on the page.
    assert "Intro to Olympiad" not in text


@pytest.mark.django_db
def test_notice_prefers_the_semester_with_something_outstanding(
    semester: Semester, student: Student, next_semester: Semester, client_for
):
    """A settled current semester does not hide next semester's paperwork."""
    complete_registration(student)
    StudentInviteLink.objects.create(
        name="Spring 2026",
        semester=next_semester,
        expiration_date=timezone.now() + timedelta(days=60),
    )
    StudentRegistration.objects.create(
        student=Student.objects.create(
            user=student.user, semester=next_semester, airtable_name="Lucy"
        ),
        completed_steps=[],
    )

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "Your registration for Spring 2026 isn't done yet" in text


@pytest.mark.django_db
def test_notice_announces_a_semester_that_has_not_opened(
    next_semester: Semester, client_for
):
    """Between semesters there is nothing to be enrolled in, so say what's next."""
    User.objects.create_user(username="stranger", password="password")

    text = visible_text(client_for("stranger").get(reverse("index")).content.decode())

    start = date_filter(next_semester.start_date, "F j, Y")
    assert "The session Spring 2026 hasn't started yet!" in text
    assert f"It is scheduled to start on {start}." in text
    # "the current session" would be a lie while none is running.
    assert "You don't seem to be enrolled" not in text


@pytest.mark.django_db
def test_notice_announces_the_opening_to_an_assigned_student_too(
    next_semester: Semester, client_for
):
    """Classes exist but the course lists only carry the running semester, so a
    fully sorted student still faces a blank dashboard until it opens."""
    user = User.objects.create_user(username="lucy", password="password")
    student = Student.objects.create(
        user=user, semester=next_semester, airtable_name="Lucy"
    )
    complete_registration(student)
    course = Course.objects.create(
        name="Intro to Olympiad", description="", semester=next_semester
    )
    course.students.add(student)

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "The session Spring 2026 hasn't started yet!" in text


@pytest.mark.django_db
def test_notice_stays_quiet_while_a_semester_is_running(
    semester: Semester, student: Student, next_semester: Semester, client_for
):
    """A semester already underway is not something to announce."""
    complete_registration(student)

    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "hasn't started yet" not in text


@pytest.mark.django_db
def test_yearbook_keeps_showing_an_alumna_her_last_entry(client_for):
    """A student whose only semester has ended still reaches her own entry."""
    today = timezone.localdate()
    old_semester = Semester.objects.create(
        name="Spring 2025",
        slug="sp25",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=100),
    )
    user = User.objects.create_user(username="alum", password="password")
    old_student = Student.objects.create(
        user=user, semester=old_semester, airtable_name="Alum"
    )
    YearbookEntry.objects.create(
        student=old_student, display_name="Alum A.", bio="I liked combinatorics."
    )

    content = client_for("alum").get(reverse("index")).content.decode()
    text = visible_text(content)

    assert "Alum A." in text
    assert "I liked combinatorics." in text
    # Closed, so no edit button, and the heading lands in her own semester.
    assert reverse("yearbook:entry_list", kwargs={"slug": "sp25"}) in content
    assert "Edit entry" not in text


@pytest.mark.django_db
def test_yearbook_says_an_ended_semester_is_closed(client_for):
    """An alumna with no entry is told the window has shut, not invited to add."""
    today = timezone.localdate()
    old_semester = Semester.objects.create(
        name="Spring 2025",
        slug="sp25",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=100),
    )
    user = User.objects.create_user(username="alum", password="password")
    Student.objects.create(user=user, semester=old_semester, airtable_name="Alum")

    text = visible_text(client_for("alum").get(reverse("index")).content.decode())

    assert "Entries for Spring 2025 are closed." in text
    assert "Add entry" not in text


@pytest.mark.django_db
def test_yearbook_opens_before_the_semester_starts(next_semester: Semester, client_for):
    """An incoming student can write her entry ahead of the semester opening."""
    user = User.objects.create_user(username="lucy", password="password")
    student = Student.objects.create(
        user=user, semester=next_semester, airtable_name="Lucy"
    )

    client = client_for("lucy")
    content = client.get(reverse("index")).content.decode()

    assert "You don't have an entry yet for Spring 2026." in visible_text(content)
    create_url = reverse("yearbook:create", kwargs={"student_pk": student.pk})
    assert create_url in content
    # The button has to actually go somewhere she is allowed.
    assert client.get(create_url).status_code == 200


@pytest.mark.django_db
def test_yearbook_follows_the_most_recent_semester(
    semester: Semester, student: Student, next_semester: Semester, client_for
):
    """With rows in two semesters, the yearbook square tracks the later one."""
    Student.objects.create(
        user=student.user, semester=next_semester, airtable_name="Lucy"
    )
    YearbookEntry.objects.create(
        student=student, display_name="Old Lucy", bio="Last semester."
    )

    content = client_for("lucy").get(reverse("index")).content.decode()

    # The Fall 2025 entry belongs to the older row, so it is not the one shown.
    assert "Old Lucy" not in visible_text(content)
    assert "You don't have an entry yet for Spring 2026." in visible_text(content)
    assert (
        reverse("yearbook:entry_list", kwargs={"slug": next_semester.slug}) in content
    )


@pytest.mark.django_db
def test_empty_sections_say_so_when_nothing_is_running(
    next_semester: Semester, client_for
):
    """Between semesters "this semester" names nothing, so the three empty
    sections say what is actually true instead."""
    User.objects.create_user(username="stranger", password="password")

    content = client_for("stranger").get(reverse("index")).content.decode()
    text = visible_text(content)

    # Classes and Clubs share the line, so it lands twice.
    assert text.count("There is no active semester right now.") == 2
    assert "any classes this semester" not in text
    assert "any clubs this semester" not in text
    assert "a house this semester" not in text
    assert "There is no active semester, but you can browse" in text
    assert "leaderboards from all sessions" in text
    assert reverse("housepoints:leaderboard") in content


@pytest.mark.django_db
def test_empty_sections_keep_their_wording_mid_semester(
    semester: Semester, student: Student, client_for
):
    """With a semester underway, the sections still speak about it."""
    text = visible_text(client_for("lucy").get(reverse("index")).content.decode())

    assert "You are not enrolled in any classes this semester yet." in text
    assert "You have not joined any clubs this semester." in text
    assert "no active semester" not in text
