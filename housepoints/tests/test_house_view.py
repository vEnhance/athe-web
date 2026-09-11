from collections.abc import Callable
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.contrib.messages import constants as message_levels
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student
from housepoints.models import Award


def detail_url(semester: Semester, house: str = Student.House.OWL) -> str:
    return reverse(
        "housepoints:house_detail", kwargs={"slug": semester.slug, "house": house}
    )


def staff_url(semester: Semester, house: str = Student.House.OWL) -> str:
    return reverse(
        "housepoints:house_detail_staff", kwargs={"slug": semester.slug, "house": house}
    )


def categories(response) -> dict[str, int]:
    return {
        entry["display_name"]: entry["total_points"]
        for entry in response.context["category_data"]
    }


def rows(response) -> dict[str, int]:
    return {row["name"]: row["total"] for row in response.context["student_rows"]}


@pytest.fixture
def staff(athe: AtheClient, make_user: Callable[..., User]) -> User:
    return athe.login(make_user(username="staff", is_staff=True))


@pytest.mark.django_db
def test_house_detail_requires_login(athe: AtheClient, semester: Semester):
    athe.get_redirects(reverse("login"), detail_url(semester))


@pytest.mark.django_db
def test_house_detail_staff_can_access_any_house(
    athe: AtheClient, semester: Semester, staff: User
):
    response = athe.get_ok(detail_url(semester))

    assert response.context["house"] == Student.House.OWL
    assert response.context["house_display"] == "Owls"


@pytest.mark.django_db
def test_house_detail_student_can_access_own_house(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    make_student(semester, user=make_user(username="owlet"), house=Student.House.OWL)

    athe.login("owlet")
    response = athe.get_ok(detail_url(semester))

    assert response.context["house_display"] == "Owls"


@pytest.mark.django_db
def test_house_detail_student_cannot_access_other_house(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    make_student(semester, user=make_user(username="kitten"), house=Student.House.CAT)

    athe.login("kitten")
    athe.get_redirects(
        reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug}),
        detail_url(semester),
    )


@pytest.mark.django_db
def test_house_detail_shows_category_totals(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
    award: Callable[..., Award],
):
    alice = make_student(semester, house=Student.House.OWL)
    bob = make_student(semester, house=Student.House.OWL)
    award(semester, alice, award_type=Award.AwardType.CLASS_ATTENDANCE)
    award(semester, bob, award_type=Award.AwardType.CLASS_ATTENDANCE)
    award(semester, alice, award_type=Award.AwardType.HOMEWORK)

    response = athe.get_ok(detail_url(semester))

    assert categories(response) == {"Class Attendance": 10, "Homework Submission": 5}
    assert response.context["grand_total"] == 15


@pytest.mark.django_db
def test_house_detail_invalid_house(athe: AtheClient, semester: Semester, staff: User):
    url = reverse(
        "housepoints:house_detail", kwargs={"slug": semester.slug, "house": "invalid"}
    )
    response = athe.get(url, follow=True)

    assert any(m.level == message_levels.ERROR for m in response.context["messages"])


@pytest.mark.django_db
def test_house_detail_respects_freeze_date(
    athe: AtheClient,
    staff: User,
    make_semester: Callable[..., Semester],
    make_student: Callable[..., Student],
    award: Callable[..., Award],
):
    freeze = timezone.now() - timedelta(days=1)
    semester = make_semester(house_points_freeze_date=freeze)
    student = make_student(semester, house=Student.House.OWL)
    award(semester, student, points=5, awarded_at=freeze - timedelta(hours=1))
    award(semester, student, points=10, awarded_at=freeze + timedelta(hours=1))

    response = athe.get_ok(detail_url(semester))

    assert response.context["grand_total"] == 5
    assert response.context["is_frozen"] is True
    athe.assert_testid(response, "house-freeze-notice", "house-true-totals-link")


@pytest.mark.django_db
def test_house_detail_is_empty_without_awards(
    athe: AtheClient, semester: Semester, staff: User
):
    response = athe.get_ok(detail_url(semester))

    assert response.context["category_data"] == []
    athe.assert_testid(response, "house-empty")


@pytest.mark.django_db
def test_house_detail_staff_requires_staff(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    make_student(semester, user=make_user(username="owlet"), house=Student.House.OWL)

    athe.login("owlet")
    athe.get_redirects(reverse("housepoints:leaderboard"), staff_url(semester))


@pytest.mark.django_db
def test_house_detail_staff_shows_student_by_category_grid(
    athe: AtheClient,
    semester: Semester,
    staff: User,
    make_student: Callable[..., Student],
    award: Callable[..., Award],
):
    """One row per student, one column per award type actually used."""
    alice = make_student(semester, house=Student.House.OWL, airtable_name="Alice Smith")
    bob = make_student(semester, house=Student.House.OWL, airtable_name="Bob Jones")
    award(semester, alice, award_type=Award.AwardType.CLASS_ATTENDANCE, points=10)
    award(semester, alice, award_type=Award.AwardType.HOMEWORK, points=5)
    award(semester, bob, award_type=Award.AwardType.CLASS_ATTENDANCE, points=5)

    response = athe.get_ok(staff_url(semester))

    assert response.context["headers"] == ["Attend", "Hwk"]
    assert rows(response) == {"Alice Smith": 15, "Bob Jones": 5}
    assert response.context["column_totals"] == [15, 5]
    assert response.context["grand_total"] == 20


@pytest.mark.django_db
def test_house_detail_staff_includes_house_level_awards(
    athe: AtheClient, semester: Semester, staff: User, award: Callable[..., Award]
):
    """An award with no student gets a row of its own rather than being lost."""
    award(
        semester,
        house=Student.House.OWL,
        award_type=Award.AwardType.HOUSE_ACTIVITY,
        points=50,
    )

    response = athe.get_ok(staff_url(semester))

    assert rows(response) == {"(House-level awards)": 50}
    assert response.context["grand_total"] == 50


@pytest.mark.django_db
def test_house_detail_staff_invalid_house(
    athe: AtheClient, semester: Semester, staff: User
):
    url = reverse(
        "housepoints:house_detail_staff",
        kwargs={"slug": semester.slug, "house": "invalid"},
    )
    response = athe.get(url, follow=True)

    assert any(m.level == message_levels.ERROR for m in response.context["messages"])


@pytest.mark.django_db
def test_house_detail_staff_ignores_the_freeze_date(
    athe: AtheClient,
    staff: User,
    make_semester: Callable[..., Semester],
    make_student: Callable[..., Student],
    award: Callable[..., Award],
):
    """The staff grid is the true total; the banner is what says the public
    leaderboard has stopped agreeing with it."""
    freeze = timezone.now() - timedelta(days=1)
    semester = make_semester(house_points_freeze_date=freeze)
    student = make_student(semester, house=Student.House.OWL)
    award(semester, student, points=5, awarded_at=freeze - timedelta(hours=1))
    award(semester, student, points=10, awarded_at=freeze + timedelta(hours=1))

    response = athe.get_ok(staff_url(semester))

    assert response.context["grand_total"] == 15
    assert response.context["is_frozen"] is True
    athe.assert_testid(response, "house-staff-freeze-notice")


@pytest.mark.django_db
def test_house_detail_staff_empty_house(
    athe: AtheClient, semester: Semester, staff: User
):
    response = athe.get_ok(staff_url(semester))

    assert response.context["student_rows"] == []
    athe.assert_testid(response, "house-staff-empty")
