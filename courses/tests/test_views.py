from collections.abc import Callable
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Course, CourseMeeting, Semester, Student
from home.models import StaffPhotoListing


def detail_url(course: Course) -> str:
    return reverse("courses:course_detail", kwargs={"pk": course.pk})


@pytest.fixture
def course(semester: Semester, make_course: Callable[..., Course]) -> Course:
    return make_course(semester, name="Test Course")


@pytest.mark.django_db
def test_course_detail_view_staff_access(
    athe: AtheClient, course: Course, make_user: Callable[..., User]
):
    athe.login(make_user(username="staff", is_staff=True))
    athe.get_ok(detail_url(course))


@pytest.mark.django_db
def test_course_detail_view_enrolled_student_access(
    athe: AtheClient,
    semester: Semester,
    course: Course,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    user = make_user()
    course.students.add(make_student(semester, user=user))

    athe.login(user)
    athe.get_ok(detail_url(course))


@pytest.mark.django_db
def test_course_detail_view_unenrolled_student_denied(
    athe: AtheClient, course: Course, make_user: Callable[..., User]
):
    athe.login(make_user())
    assert athe.get(detail_url(course)).status_code == 403


@pytest.mark.django_db
def test_course_detail_view_lists_every_meeting(
    athe: AtheClient, course: Course, make_user: Callable[..., User]
):
    """The schedule is the whole term's, not just what is still to come; the
    next one is picked out rather than the rest being dropped."""
    past = CourseMeeting.objects.create(
        course=course,
        start_time=timezone.now() - timedelta(hours=4),
        title="Past Meeting",
    )
    future = CourseMeeting.objects.create(
        course=course,
        start_time=timezone.now() + timedelta(hours=1),
        title="Future Meeting",
    )

    athe.login(make_user(username="staff", is_staff=True))
    response = athe.get_ok(detail_url(course))

    assert list(response.context["meetings"]) == [past, future]
    assert response.context["next_meeting"] == future
    athe.assert_testid_count(response, "course-meeting-row", 2)


@pytest.mark.django_db
def test_course_detail_view_shows_instructor_photo(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_course: Callable[..., Course],
):
    instructor = StaffPhotoListing.objects.create(
        display_name="Dr. Smith",
        slug="dr-smith",
        role="Instructor",
        category=StaffPhotoListing.Category.INSTRUCTOR,
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )
    course = make_course(semester, instructor=instructor)

    athe.login(make_user(username="staff", is_staff=True))
    response = athe.get_ok(detail_url(course))

    athe.assert_testid(response, "course-instructor-aside")
    assert instructor.photo.url.encode() in response.content


@pytest.mark.django_db
def test_course_detail_view_without_instructor_has_no_photo(
    athe: AtheClient, course: Course, make_user: Callable[..., User]
):
    athe.login(make_user(username="staff", is_staff=True))
    response = athe.get_ok(detail_url(course))

    athe.assert_no_testid(response, "course-instructor-aside")
