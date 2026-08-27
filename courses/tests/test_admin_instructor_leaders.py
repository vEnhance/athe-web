"""Admin-side upkeep of the rule that a course's instructor leads it."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone

from courses.models import Course, Semester
from home.models import StaffPhotoListing

CHANGELIST_URL = "/admin/courses/course/"
ADD_URL = "/admin/courses/course/add/"


@pytest.fixture
def semester() -> Semester:
    return Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.localdate(),
        end_date=timezone.localdate() + timedelta(days=90),
    )


def make_listing(slug: str, *, with_user: bool = True) -> StaffPhotoListing:
    user = (
        User.objects.create_user(username=slug, password="password")
        if with_user
        else None
    )
    return StaffPhotoListing.objects.create(
        user=user,
        display_name=slug.title(),
        slug=slug,
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )


@pytest.fixture
def admin_client() -> Client:
    User.objects.create_superuser(username="root", password="password")
    client = Client()
    client.login(username="root", password="password")
    return client


def course_form_data(semester: Semester, **overrides: object) -> dict[str, object]:
    """A complete change-form POST, leaders box empty unless overridden."""
    data: dict[str, object] = {
        "name": "Advanced Math",
        "description": "Advanced math course",
        "semester": semester.pk,
        "instructor": "",
        "leaders": [],
        "students": [],
        "difficulty": "",
        "lesson_plan": "",
        "regular_meeting_time": "",
        "google_classroom_direct_link": "",
        "zoom_meeting_link": "",
        "discord_webhook": "",
        "discord_role_id": "",
        "meetings-TOTAL_FORMS": "0",
        "meetings-INITIAL_FORMS": "0",
        "meetings-MIN_NUM_FORMS": "0",
        "meetings-MAX_NUM_FORMS": "1000",
        "_save": "Save",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_admin_add_keeps_instructor_as_leader(admin_client, semester):
    """Adding a course in the admin leaves the instructor leading it.

    The leaders box starts empty on the add form, and the admin saves it after
    ``Course.save`` has added the instructor, so without the ``save_related``
    override this write wipes the instructor back out.
    """
    listing = make_listing("dr-smith")

    response = admin_client.post(
        ADD_URL, course_form_data(semester, instructor=listing.pk)
    )

    assert response.status_code == 302
    course = Course.objects.get(name="Advanced Math")
    assert list(course.leaders.all()) == [listing.user]


@pytest.mark.django_db
def test_admin_change_keeps_new_instructor_as_leader(admin_client, semester):
    """Switching instructors in the admin makes the new one a leader too."""
    old = make_listing("dr-old")
    new = make_listing("dr-new")
    course = Course.objects.create(
        name="Advanced Math",
        description="Advanced math course",
        semester=semester,
        instructor=old,
    )

    response = admin_client.post(
        f"{CHANGELIST_URL}{course.pk}/change/",
        course_form_data(
            semester,
            instructor=new.pk,
            leaders=[old.user.pk],  # type: ignore[union-attr]
        ),
    )

    assert response.status_code == 302
    assert set(course.leaders.all()) == {old.user, new.user}


@pytest.mark.django_db
def test_admin_change_can_still_remove_a_leader(admin_client, semester):
    """The leaders box still governs everyone who is not the instructor."""
    listing = make_listing("dr-smith")
    helper = User.objects.create_user(username="helper", password="password")
    course = Course.objects.create(
        name="Advanced Math",
        description="Advanced math course",
        semester=semester,
        instructor=listing,
    )
    course.leaders.add(helper)

    response = admin_client.post(
        f"{CHANGELIST_URL}{course.pk}/change/",
        course_form_data(
            semester,
            instructor=listing.pk,
            leaders=[listing.user.pk],  # type: ignore[union-attr]
        ),
    )

    assert response.status_code == 302
    assert list(course.leaders.all()) == [listing.user]


@pytest.mark.django_db
def test_repair_action_adds_missing_instructors(admin_client, semester):
    """The action puts the instructor back on every selected course."""
    listings = [make_listing(f"dr-{i}") for i in range(2)]
    courses = [
        Course.objects.create(
            name=f"Course {i}",
            description="desc",
            semester=semester,
            instructor=listing,
        )
        for i, listing in enumerate(listings)
    ]
    # Simulate the damage a pre-fix admin save did.
    for course in courses:
        course.leaders.clear()

    response = admin_client.post(
        CHANGELIST_URL,
        {
            "action": "add_instructor_to_leaders",
            "_selected_action": [str(course.pk) for course in courses],
        },
        follow=True,
    )

    assert response.status_code == 200
    for course, listing in zip(courses, listings, strict=True):
        assert list(course.leaders.all()) == [listing.user]
    assert "Added the instructor as a leader on 2 course(s)" in response.text


@pytest.mark.django_db
def test_repair_action_leaves_other_leaders_and_courses_alone(admin_client, semester):
    """Repairing adds the instructor without disturbing anything else."""
    listing = make_listing("dr-smith")
    helper = User.objects.create_user(username="helper", password="password")
    broken = Course.objects.create(
        name="Broken",
        description="desc",
        semester=semester,
        instructor=listing,
    )
    broken.leaders.set([helper])
    untouched = Course.objects.create(
        name="Untouched",
        description="desc",
        semester=semester,
        instructor=listing,
    )
    untouched.leaders.clear()

    admin_client.post(
        CHANGELIST_URL,
        {
            "action": "add_instructor_to_leaders",
            "_selected_action": [str(broken.pk)],
        },
        follow=True,
    )

    assert set(broken.leaders.all()) == {helper, listing.user}
    assert list(untouched.leaders.all()) == []


@pytest.mark.django_db
def test_repair_action_reports_courses_with_no_instructor_account(
    admin_client, semester
):
    """Courses the action cannot help are named rather than silently skipped."""
    no_instructor = Course.objects.create(
        name="No instructor", description="desc", semester=semester
    )
    no_account = Course.objects.create(
        name="No account",
        description="desc",
        semester=semester,
        instructor=make_listing("dr-guest", with_user=False),
    )

    response = admin_client.post(
        CHANGELIST_URL,
        {
            "action": "add_instructor_to_leaders",
            "_selected_action": [str(no_instructor.pk), str(no_account.pk)],
        },
        follow=True,
    )

    assert response.status_code == 200
    assert "Added the instructor as a leader on 0 course(s)" in response.text
    assert "No instructor account to add for" in response.text
    assert str(no_instructor) in response.text
    assert str(no_account) in response.text


@pytest.mark.django_db
def test_ensure_instructor_is_leader_reports_whether_it_changed_anything(semester):
    """The model helper only claims a repair when it actually made one."""
    listing = make_listing("dr-smith")
    course = Course.objects.create(
        name="Advanced Math",
        description="desc",
        semester=semester,
        instructor=listing,
    )

    assert course.ensure_instructor_is_leader() is False  # save() already did it
    course.leaders.clear()
    assert course.ensure_instructor_is_leader() is True
    assert course.ensure_instructor_is_leader() is False
