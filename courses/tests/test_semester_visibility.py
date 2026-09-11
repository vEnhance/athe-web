from collections.abc import Callable
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Course, Semester, Student

SEMESTER_LIST = reverse("courses:semester_list")


def course_list_url(semester: Semester) -> str:
    return reverse("courses:course_list", kwargs={"slug": semester.slug})


@pytest.fixture
def invisible(make_semester: Callable[..., Semester]) -> Semester:
    today = timezone.localdate()
    return make_semester(
        name="Invisible Semester",
        start_date=today + timedelta(days=120),
        end_date=today + timedelta(days=210),
        visible=False,
    )


@pytest.mark.django_db
def test_semester_list_hides_invisible_from_non_staff(
    athe: AtheClient,
    semester: Semester,
    invisible: Semester,
    make_user: Callable[..., User],
):
    athe.login(make_user())
    response = athe.get_ok(SEMESTER_LIST)

    assert [s.name for s in response.context["semesters"]] == [semester.name]


@pytest.mark.django_db
def test_semester_list_shows_all_to_staff(
    athe: AtheClient,
    semester: Semester,
    invisible: Semester,
    make_user: Callable[..., User],
):
    athe.login(make_user(username="staff", is_staff=True))
    response = athe.get_ok(SEMESTER_LIST)

    assert {s.name for s in response.context["semesters"]} == {
        semester.name,
        invisible.name,
    }


@pytest.mark.django_db
def test_course_list_invisible_semester_non_staff_404(
    athe: AtheClient, invisible: Semester, make_user: Callable[..., User]
):
    athe.login(make_user())
    assert athe.get(course_list_url(invisible)).status_code == 404


@pytest.mark.django_db
def test_course_list_invisible_semester_staff_access(
    athe: AtheClient,
    invisible: Semester,
    make_user: Callable[..., User],
    make_course: Callable[..., Course],
):
    course = make_course(invisible, name="Test Course")

    athe.login(make_user(username="staff", is_staff=True))
    response = athe.get_ok(course_list_url(invisible))

    assert list(response.context["courses"]) == [course]


@pytest.mark.django_db
def test_course_detail_invisible_semester_non_staff_denied(
    athe: AtheClient,
    invisible: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
    make_course: Callable[..., Course],
):
    """Enrolment is not enough: a semester kept back is kept back from its own
    students too."""
    user = make_user()
    course = make_course(invisible)
    course.students.add(make_student(invisible, user=user))

    athe.login(user)
    url = reverse("courses:course_detail", kwargs={"pk": course.pk})
    assert athe.get(url).status_code == 403


@pytest.mark.django_db
def test_course_detail_invisible_semester_staff_access(
    athe: AtheClient,
    invisible: Semester,
    make_user: Callable[..., User],
    make_course: Callable[..., Course],
):
    course = make_course(invisible)

    athe.login(make_user(username="staff", is_staff=True))
    athe.get_ok(reverse("courses:course_detail", kwargs={"pk": course.pk}))


@pytest.mark.django_db
def test_catalog_root_skips_invisible_for_non_staff(
    athe: AtheClient,
    past_semester: Semester,
    make_semester: Callable[..., Semester],
    make_user: Callable[..., User],
):
    make_semester(name="Newer Invisible", visible=False)

    athe.login(make_user())
    athe.get_redirects(course_list_url(past_semester), reverse("courses:catalog_root"))


@pytest.mark.django_db
def test_catalog_root_includes_invisible_for_staff(
    athe: AtheClient,
    past_semester: Semester,
    make_semester: Callable[..., Semester],
    make_user: Callable[..., User],
):
    newer = make_semester(name="Newer Invisible", visible=False)

    athe.login(make_user(username="staff", is_staff=True))
    athe.get_redirects(course_list_url(newer), reverse("courses:catalog_root"))


@pytest.fixture
def three_semesters(
    make_semester: Callable[..., Semester],
) -> tuple[Semester, Semester, Semester]:
    """Visible, invisible, visible, in chronological order."""
    today = timezone.localdate()
    older = make_semester(
        name="Older Visible",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=110),
    )
    middle = make_semester(
        name="Middle Invisible",
        start_date=today - timedelta(days=100),
        end_date=today - timedelta(days=10),
        visible=False,
    )
    newer = make_semester(name="Newer Visible")
    return older, middle, newer


@pytest.mark.django_db
def test_course_list_navigation_skips_invisible_for_non_staff(
    athe: AtheClient,
    three_semesters: tuple[Semester, Semester, Semester],
    make_user: Callable[..., User],
):
    older, _, newer = three_semesters

    athe.login(make_user())

    response = athe.get_ok(course_list_url(newer))
    assert response.context["prev_semester"] == older
    assert response.context["next_semester"] is None

    response = athe.get_ok(course_list_url(older))
    assert response.context["prev_semester"] is None
    assert response.context["next_semester"] == newer


@pytest.mark.django_db
def test_course_list_navigation_includes_invisible_for_staff(
    athe: AtheClient,
    three_semesters: tuple[Semester, Semester, Semester],
    make_user: Callable[..., User],
):
    older, middle, newer = three_semesters

    athe.login(make_user(username="staff", is_staff=True))

    response = athe.get_ok(course_list_url(newer))
    assert response.context["prev_semester"] == middle
    assert response.context["next_semester"] is None

    response = athe.get_ok(course_list_url(middle))
    assert response.context["prev_semester"] == older
    assert response.context["next_semester"] == newer
