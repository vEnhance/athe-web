"""Who may edit a course, now that saying so is not a per-course list."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ValidationError
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
def test_subscribing_to_a_class_does_not_grant_editing(semester, staff_user):
    """Following is about someone's own pages; it is not a claim to the course."""
    teacher = staff_user("teacher")
    follower = staff_user("follower")
    course = make_course(semester, instructor=teacher.staffphotolisting)
    course.subscribed_staff.add(follower.staffphotolisting)

    assert course.is_followed_by(follower)
    assert not course.is_run_by(follower)
    assert not course.is_managed_by(follower)


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
def test_followed_by_covers_teaching_and_subscribing(semester, staff_user):
    teacher = staff_user("teacher")
    follower = staff_user("follower")
    bystander = staff_user("bystander")
    taught = make_course(semester, instructor=teacher.staffphotolisting)
    followed = make_course(semester, name="Number Theory")
    followed.subscribed_staff.add(follower.staffphotolisting)

    assert list(Course.objects.followed_by(teacher)) == [taught]
    assert list(Course.objects.followed_by(follower)) == [followed]
    assert list(Course.objects.followed_by(bystander)) == []
    assert list(Course.objects.followed_by(AnonymousUser())) == []
    # Teaching is the narrower question, and a subscription is not an answer.
    assert list(Course.objects.taught_by(teacher)) == [taught]
    assert list(Course.objects.taught_by(follower)) == []


@pytest.mark.django_db
def test_for_user_covers_enrolment_and_running_without_duplicates(semester, staff_user):
    teacher = staff_user("teacher")
    taught = make_course(semester, instructor=teacher.staffphotolisting)
    # A staff member with a Student row for the same course must not see it twice.
    taught.students.add(Student.objects.create(user=teacher, semester=semester))

    assert list(Course.objects.for_user(teacher)) == [taught]


@pytest.mark.django_db
def test_a_subscription_is_not_published_on_the_staff_page(semester, staff_user):
    """Following a club is a private choice, not a credit anyone else sees."""
    follower = staff_user("follower")
    club = make_course(semester, name="Japanese Club", is_club=True)
    club.subscribed_staff.add(follower.staffphotolisting)

    client = Client()
    response = client.get(follower.staffphotolisting.get_absolute_url())

    assert response.status_code == 200
    assert "Japanese Club" not in response.text


# --- the club page a staff member sees -------------------------------------


@pytest.mark.django_db
def test_my_clubs_offers_staff_subscribing_rather_than_joining(semester, staff_user):
    """Joining means a Student row, which is a different thing staff may have."""
    follower = staff_user("follower")
    mine = make_course(semester, name="Japanese Club", is_club=True)
    mine.subscribed_staff.add(follower.staffphotolisting)
    other = make_course(semester, name="Chess Club", is_club=True)

    client = Client()
    client.force_login(follower)
    response = client.get(reverse("courses:my_clubs"))

    assert response.status_code == 200
    assert "Clubs You Follow" in response.text
    assert (
        reverse("courses:unsubscribe_course", kwargs={"pk": mine.pk}) in response.text
    )
    assert reverse("courses:subscribe_course", kwargs={"pk": other.pk}) in response.text
    assert reverse("courses:join_club", kwargs={"pk": other.pk}) not in response.text


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
    club.subscribed_staff.add(second.staffphotolisting, third.staffphotolisting)
    CourseMeeting.objects.create(
        course=club,
        start_time=timezone.now() + timedelta(days=1),
        title="Kanji practice",
    )
    return club, [lead, second, third]


@pytest.mark.django_db
def test_every_staff_member_following_a_club_gets_it_on_my_clubs(club_run_by_three):
    club, runners = club_run_by_three

    for user in runners:
        client = Client()
        client.force_login(user)
        response = client.get(reverse("courses:my_clubs"))
        assert club.name in response.text, f"{user.username} does not see the club"


@pytest.mark.django_db
def test_every_staff_member_following_a_club_gets_it_on_the_dashboard(
    club_run_by_three,
):
    club, runners = club_run_by_three

    for user in runners:
        client = Client()
        client.force_login(user)
        response = client.get(reverse("index"))
        assert club.name in response.text, f"{user.username} does not see the club"


@pytest.mark.django_db
def test_every_staff_member_following_a_club_gets_its_meetings_on_the_calendar(
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
def test_every_staff_member_following_a_club_gets_it_in_their_ical_feed(
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


# --- the rare student-led club ---------------------------------------------


@pytest.fixture
def student_led_club(semester):
    """A club a student runs, with no staff attached to it at all."""
    kid = User.objects.create_user(username="kid", password="password")
    student = Student.objects.create(user=kid, semester=semester)
    club = make_course(semester, name="Japanese Club", is_club=True)
    club.students.add(student)
    club.student_organizers.add(student)
    return club, kid


@pytest.mark.django_db
def test_a_student_organizer_may_edit_their_own_club(student_led_club):
    club, kid = student_led_club

    assert club.is_organized_by(kid)
    assert club.is_managed_by(kid)


@pytest.mark.django_db
def test_a_student_organizer_gets_no_reach_beyond_that_club(student_led_club, semester):
    """The grant is one club wide, unlike the blanket one staff get."""
    _, kid = student_led_club
    other_club = make_course(semester, name="Chess Club", is_club=True)
    other_class = make_course(semester, name="Combo Heuristics")

    assert not other_club.is_managed_by(kid)
    assert not other_class.is_managed_by(kid)


@pytest.mark.django_db
def test_a_student_organizer_is_not_staff(student_led_club):
    """Organising a club must not turn into a staff account or a staff listing."""
    _, kid = student_led_club

    assert not kid.is_staff
    assert not StaffPhotoListing.objects.filter(user=kid).exists()
    assert not StaffPhotoListing.is_current_staff(kid)


@pytest.mark.django_db
def test_a_student_organizer_may_manage_the_club_meetings(student_led_club):
    club, kid = student_led_club

    client = Client()
    client.force_login(kid)
    response = client.get(reverse("courses:manage_meetings", kwargs={"pk": club.pk}))

    assert response.status_code == 200


@pytest.mark.django_db
def test_a_student_organizer_is_credited_on_the_club_page(student_led_club):
    club, kid = student_led_club
    kid.first_name, kid.last_name = "Kid", "Ohtani"
    kid.save()

    client = Client()
    client.force_login(kid)
    response = client.get(club.get_absolute_url())

    assert "Student Organizers:" in response.text
    assert "Kid Ohtani" in response.text


@pytest.mark.django_db
def test_organizers_from_another_semester_are_rejected(semester, finished_semester):
    """Same rule the enrolled students already follow."""
    kid = User.objects.create_user(username="kid", password="password")
    club = make_course(semester, name="Japanese Club", is_club=True)
    club.student_organizers.add(
        Student.objects.create(user=kid, semester=finished_semester)
    )

    with pytest.raises(ValidationError, match="are not in Fall 2025"):
        club.full_clean()


# --- subscribing and unsubscribing -----------------------------------------


@pytest.mark.django_db
def test_staff_can_subscribe_and_unsubscribe_from_the_course_page(semester, staff_user):
    follower = staff_user("follower")
    club = make_course(semester, name="Japanese Club", is_club=True)

    client = Client()
    client.force_login(follower)
    client.post(reverse("courses:subscribe_course", kwargs={"pk": club.pk}))
    assert club.is_followed_by(follower)

    client.post(reverse("courses:unsubscribe_course", kwargs={"pk": club.pk}))
    assert not club.is_followed_by(follower)


@pytest.mark.django_db
def test_staff_can_subscribe_to_a_class_too(semester, staff_user):
    """Uncommon, but nothing about following is club-specific."""
    follower = staff_user("follower")
    klass = make_course(semester, instructor=staff_user("teacher").staffphotolisting)

    client = Client()
    client.force_login(follower)
    response = client.post(
        reverse("courses:subscribe_course", kwargs={"pk": klass.pk}), follow=True
    )

    assert response.status_code == 200
    assert klass.is_followed_by(follower)
    assert list(Course.objects.for_user(follower)) == [klass]


@pytest.mark.django_db
def test_subscribing_twice_is_harmless(semester, staff_user):
    follower = staff_user("follower")
    club = make_course(semester, name="Japanese Club", is_club=True)

    client = Client()
    client.force_login(follower)
    for _ in range(2):
        client.post(reverse("courses:subscribe_course", kwargs={"pk": club.pk}))

    assert club.subscribed_staff.count() == 1


@pytest.mark.django_db
def test_a_student_cannot_subscribe(semester):
    """Following is the staff-side counterpart of joining, not an extra way in."""
    kid = User.objects.create_user(username="kid", password="password")
    Student.objects.create(user=kid, semester=semester)
    club = make_course(semester, name="Japanese Club", is_club=True)

    client = Client()
    client.force_login(kid)
    response = client.post(
        reverse("courses:subscribe_course", kwargs={"pk": club.pk}), follow=True
    )

    assert club.subscribed_staff.count() == 0
    assert "Only current staff can follow a course." in response.text


@pytest.mark.django_db
def test_past_staff_cannot_subscribe(semester, staff_user):
    alum = staff_user("alum", category=StaffPhotoListing.Category.XSTAFF)
    club = make_course(semester, name="Japanese Club", is_club=True)

    client = Client()
    client.force_login(alum)
    client.post(reverse("courses:subscribe_course", kwargs={"pk": club.pk}))

    assert club.subscribed_staff.count() == 0


@pytest.mark.django_db
def test_subscribing_needs_a_post(semester, staff_user):
    follower = staff_user("follower")
    club = make_course(semester, name="Japanese Club", is_club=True)

    client = Client()
    client.force_login(follower)
    response = client.get(reverse("courses:subscribe_course", kwargs={"pk": club.pk}))

    assert response.status_code == 405


@pytest.mark.django_db
def test_a_staff_members_dummy_student_row_is_left_alone(semester, staff_user):
    """Some staff keep a Student row for testing; following must not touch it."""
    follower = staff_user("follower")
    dummy = Student.objects.create(user=follower, semester=semester)
    club = make_course(semester, name="Japanese Club", is_club=True)
    club.students.add(dummy)

    client = Client()
    client.force_login(follower)
    client.post(reverse("courses:subscribe_course", kwargs={"pk": club.pk}))
    client.post(reverse("courses:unsubscribe_course", kwargs={"pk": club.pk}))

    assert list(club.students.all()) == [dummy]
    assert not club.is_followed_by(follower)


@pytest.mark.django_db
def test_the_course_page_offers_staff_the_right_button(semester, staff_user):
    follower = staff_user("follower")
    club = make_course(semester, name="Japanese Club", is_club=True)

    client = Client()
    client.force_login(follower)
    assert "Subscribe to this" in client.get(club.get_absolute_url()).text

    club.subscribed_staff.add(follower.staffphotolisting)
    assert "Unsubscribe from this" in client.get(club.get_absolute_url()).text


@pytest.mark.django_db
def test_the_course_page_offers_students_join_by_post(semester):
    """The Join and Drop controls must post: both views require it."""
    kid = User.objects.create_user(username="kid", password="password")
    Student.objects.create(user=kid, semester=semester)
    club = make_course(semester, name="Japanese Club", is_club=True)

    client = Client()
    client.force_login(kid)
    page = client.get(club.get_absolute_url()).text

    assert f'action="{reverse("courses:join_club", kwargs={"pk": club.pk})}"' in page
    assert "Subscribe to this" not in page
