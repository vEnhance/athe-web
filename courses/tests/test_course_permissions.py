"""Who may edit a course, now that saying so is not a per-course list."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import CalendarToken, Course, CourseMeeting, Semester, Student
from home.models import StaffPhotoListing


@pytest.fixture
def semester() -> Semester:
    return Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.localdate() - timedelta(days=10),
        end_date=timezone.localdate() + timedelta(days=80),
    )


@pytest.fixture
def finished_semester() -> Semester:
    return Semester.objects.create(
        name="Spring 2024",
        slug="sp24",
        start_date=timezone.localdate() - timedelta(days=400),
        end_date=timezone.localdate() - timedelta(days=300),
    )


@pytest.fixture
def staff_user(staff_listing_for):
    """A registered staff member with a current listing, running nothing."""

    def _make(username: str, **kwargs) -> User:
        user = User.objects.create_user(
            username=username, password="password", is_staff=True
        )
        staff_listing_for(user, **kwargs)
        return user

    return _make


def make_course(semester: Semester, **kwargs) -> Course:
    defaults = {"name": "Combo Heuristics", "description": "desc"}
    return Course.objects.create(semester=semester, **(defaults | kwargs))


# --- classes: the instructor and the superuser, and nobody else -------------


@pytest.mark.django_db
def test_instructor_manages_their_own_class(semester, staff_user):
    teacher = staff_user("teacher")
    course = make_course(semester, instructor=teacher.staffphotolisting)

    assert course.is_run_by(teacher)
    assert course.is_managed_by(teacher)


@pytest.mark.django_db
def test_other_staff_cannot_edit_a_class_they_do_not_teach(semester, staff_user):
    teacher = staff_user("teacher")
    bystander = staff_user("bystander")
    course = make_course(semester, instructor=teacher.staffphotolisting)

    assert not course.is_managed_by(bystander)


@pytest.mark.django_db
def test_co_instructor_manages_the_class(semester, staff_user):
    teacher = staff_user("teacher")
    helper = staff_user("helper")
    course = make_course(semester, instructor=teacher.staffphotolisting)
    course.co_instructors.add(helper.staffphotolisting)

    assert course.is_run_by(helper)
    assert course.is_managed_by(helper)


@pytest.mark.django_db
def test_superuser_manages_anything(semester, staff_user):
    root = User.objects.create_superuser(username="root", password="password")
    course = make_course(semester, instructor=staff_user("teacher").staffphotolisting)

    assert course.is_managed_by(root)


# --- clubs: any current staff member, while the semester is still running ---


@pytest.mark.django_db
def test_any_current_staff_member_edits_an_active_club(semester, staff_user):
    bystander = staff_user("bystander")
    club = make_course(semester, name="Japanese Club", is_club=True)

    assert not club.is_run_by(bystander)
    assert club.is_managed_by(bystander)


@pytest.mark.django_db
def test_past_staff_cannot_edit_a_club(semester, staff_user):
    alum = staff_user("alum", category=StaffPhotoListing.Category.XSTAFF)
    club = make_course(semester, name="Japanese Club", is_club=True)

    assert not club.is_managed_by(alum)


@pytest.mark.django_db
def test_staff_cannot_edit_a_club_from_a_finished_semester(
    finished_semester, staff_user
):
    bystander = staff_user("bystander")
    club = make_course(finished_semester, name="Japanese Club", is_club=True)

    assert not club.is_managed_by(bystander)


@pytest.mark.django_db
def test_whoever_ran_a_finished_club_still_can(finished_semester, staff_user):
    """Running it beats the semester window, so old material stays fixable."""
    teacher = staff_user("teacher")
    club = make_course(
        finished_semester,
        name="Japanese Club",
        is_club=True,
        instructor=teacher.staffphotolisting,
    )

    assert club.is_managed_by(teacher)


@pytest.mark.django_db
def test_a_flag_alone_is_not_enough_without_a_listing(semester):
    """``is_staff`` used to grant everything; a current listing is the test now."""
    flagged = User.objects.create_user(
        username="flagged", password="password", is_staff=True
    )
    club = make_course(semester, name="Japanese Club", is_club=True)

    assert not club.is_managed_by(flagged)


# --- students and strangers ------------------------------------------------


@pytest.mark.django_db
def test_enrolled_student_cannot_edit_their_club(semester):
    kid = User.objects.create_user(username="kid", password="password")
    club = make_course(semester, name="Japanese Club", is_club=True)
    club.students.add(Student.objects.create(user=kid, semester=semester))

    assert not club.is_managed_by(kid)


@pytest.mark.django_db
def test_anonymous_users_manage_nothing(semester):
    club = make_course(semester, name="Japanese Club", is_club=True)

    assert not club.is_managed_by(AnonymousUser())
    assert not club.is_run_by(AnonymousUser())


# --- the querysets that decide whose course it is --------------------------


@pytest.mark.django_db
def test_run_by_covers_instructors_and_co_instructors(semester, staff_user):
    teacher = staff_user("teacher")
    helper = staff_user("helper")
    bystander = staff_user("bystander")
    taught = make_course(semester, instructor=teacher.staffphotolisting)
    helped = make_course(semester, name="Number Theory")
    helped.co_instructors.add(helper.staffphotolisting)

    assert list(Course.objects.run_by(teacher)) == [taught]
    assert list(Course.objects.run_by(helper)) == [helped]
    assert list(Course.objects.run_by(bystander)) == []
    assert list(Course.objects.run_by(AnonymousUser())) == []


@pytest.mark.django_db
def test_for_user_covers_enrolment_and_running_without_duplicates(semester, staff_user):
    teacher = staff_user("teacher")
    taught = make_course(semester, instructor=teacher.staffphotolisting)
    # A staff member with a Student row for the same course must not see it twice.
    taught.students.add(Student.objects.create(user=teacher, semester=semester))

    assert list(Course.objects.for_user(teacher)) == [taught]


@pytest.mark.django_db
def test_a_co_instructed_course_is_listed_on_the_staff_page(semester, staff_user):
    helper = staff_user("helper")
    club = make_course(semester, name="Japanese Club", is_club=True)
    club.co_instructors.add(helper.staffphotolisting)

    client = Client()
    response = client.get(helper.staffphotolisting.get_absolute_url())

    assert response.status_code == 200
    assert "Japanese Club" in response.text


# --- the club page a staff member sees -------------------------------------


@pytest.mark.django_db
def test_my_clubs_shows_staff_the_clubs_they_run_and_no_join_buttons(
    semester, staff_user
):
    """Staff have no Student row, so a Join button could only ever fail."""
    helper = staff_user("helper")
    mine = make_course(semester, name="Japanese Club", is_club=True)
    mine.co_instructors.add(helper.staffphotolisting)
    make_course(semester, name="Chess Club", is_club=True)

    client = Client()
    client.force_login(helper)
    response = client.get(reverse("courses:my_clubs"))

    assert response.status_code == 200
    assert "Clubs You Run" in response.text
    assert "Japanese Club" in response.text
    assert "Chess Club" not in response.text
    assert reverse("courses:join_club", kwargs={"pk": mine.pk}) not in response.text


@pytest.mark.django_db
def test_staff_can_still_read_a_class_they_do_not_teach(semester, staff_user):
    """Tightening editing must not take away staff's read access."""
    course = make_course(semester, instructor=staff_user("teacher").staffphotolisting)
    bystander = staff_user("bystander")

    client = Client()
    client.force_login(bystander)
    response = client.get(course.get_absolute_url())

    assert response.status_code == 200
    assert "Edit Course" not in response.text


# --- a club run by several people is everyone's, on every list -------------


@pytest.fixture
def club_run_by_three(semester, staff_user):
    """One club, a lead and two others, which is the case this exists for."""
    lead = staff_user("lead")
    second = staff_user("second")
    third = staff_user("third")
    club = make_course(
        semester,
        name="Japanese Club",
        is_club=True,
        instructor=lead.staffphotolisting,
    )
    club.co_instructors.add(second.staffphotolisting, third.staffphotolisting)
    CourseMeeting.objects.create(
        course=club,
        start_time=timezone.now() + timedelta(days=1),
        title="Kanji practice",
    )
    return club, [lead, second, third]


@pytest.mark.django_db
def test_every_staff_member_running_a_club_gets_it_on_my_clubs(club_run_by_three):
    club, runners = club_run_by_three

    for user in runners:
        client = Client()
        client.force_login(user)
        response = client.get(reverse("courses:my_clubs"))
        assert club.name in response.text, f"{user.username} does not see the club"


@pytest.mark.django_db
def test_every_staff_member_running_a_club_gets_it_on_the_dashboard(club_run_by_three):
    club, runners = club_run_by_three

    for user in runners:
        client = Client()
        client.force_login(user)
        response = client.get(reverse("index"))
        assert club.name in response.text, f"{user.username} does not see the club"


@pytest.mark.django_db
def test_every_staff_member_running_a_club_gets_its_meetings_on_the_calendar(
    club_run_by_three,
):
    club, runners = club_run_by_three

    for user in runners:
        client = Client()
        client.force_login(user)
        response = client.get(reverse("courses:calendar"))
        assert response.status_code == 200
        # ``enrolled_club`` is the shading for a club that is yours; the
        # fallback category for someone else's club is ``other_club``.
        categories = {
            event["category"]
            for week in response.context["weeks_data"]
            for day in week
            for event in day["events"]
            if event["title"].startswith(club.name)
        }
        assert categories == {"enrolled_club"}, f"{user.username} got {categories}"


@pytest.mark.django_db
def test_every_staff_member_running_a_club_gets_it_in_their_ical_feed(
    club_run_by_three,
):
    club, runners = club_run_by_three

    for user in runners:
        token = CalendarToken.objects.create(user=user)
        response = Client().get(
            reverse("courses:calendar-feed", kwargs={"token": token.token})
        )
        assert response.status_code == 200
        feed = response.content.decode()
        assert f"{club.name}: Kanji practice" in feed, f"missing for {user.username}"
