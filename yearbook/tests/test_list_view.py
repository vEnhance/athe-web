from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student
from yearbook.models import YearbookEntry


def list_url(semester: Semester) -> str:
    return reverse("yearbook:entry_list", kwargs={"slug": semester.slug})


def displayed(response) -> list[str]:
    return [entry.display_name for entry in response.context["entries"]]


@pytest.fixture
def student(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
) -> Student:
    student = make_student(semester, user=make_user())
    athe.login(student.user)
    return student


@pytest.mark.django_db
def test_entry_list_requires_login(athe: AtheClient, semester: Semester):
    athe.get_redirects(reverse("login"), list_url(semester))


@pytest.mark.django_db
def test_entry_list_staff_can_access_any_semester(
    athe: AtheClient, semester: Semester, make_user: Callable[..., User]
):
    athe.login(make_user(username="staff", is_staff=True))
    athe.get_ok(list_url(semester))


@pytest.mark.django_db
def test_entry_list_student_in_semester_can_access(
    athe: AtheClient, semester: Semester, student: Student
):
    response = athe.get_ok(list_url(semester))

    assert response.context["user_student"] == student


@pytest.mark.django_db
def test_entry_list_student_not_in_semester_denied(
    athe: AtheClient,
    semester: Semester,
    past_semester_for_yearbook: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    user = make_user(username="outsider")
    make_student(past_semester_for_yearbook, user=user)

    athe.login(user)
    assert athe.get(list_url(semester)).status_code == 403


@pytest.mark.django_db
def test_entry_list_user_without_student_denied(
    athe: AtheClient, semester: Semester, make_user: Callable[..., User]
):
    athe.login(make_user(username="regular"))
    assert athe.get(list_url(semester)).status_code == 403


@pytest.mark.django_db
def test_entry_list_is_readable_with_no_entries_at_all(
    athe: AtheClient, semester: Semester, student: Student
):
    response = athe.get_ok(list_url(semester))

    assert displayed(response) == []
    athe.assert_testid(response, "yearbook-list-empty")


@pytest.mark.django_db
def test_entry_list_groups_entries_by_house(
    athe: AtheClient,
    semester: Semester,
    student: Student,
    make_student: Callable[..., Student],
    make_entry: Callable[..., YearbookEntry],
):
    """Entries are grouped under a heading per house, houses in declared order."""
    for house, name in (
        (Student.House.CAT, "Cat Person"),
        (Student.House.BLOB, "Blob Person"),
        (Student.House.OWL, "Owl Person"),
    ):
        make_entry(make_student(semester, house=house), display_name=name)

    response = athe.get_ok(list_url(semester))

    assert displayed(response) == ["Blob Person", "Cat Person", "Owl Person"]
    assert athe.texts_of(response, "yearbook-house-heading") == [
        "Blobs",
        "Cats",
        "Owls",
    ]


@pytest.mark.django_db
def test_entry_list_offers_to_create_an_entry(
    athe: AtheClient, semester: Semester, student: Student
):
    response = athe.get_ok(list_url(semester))

    assert response.context["can_edit"] is True
    assert response.context["has_entry"] is False
    athe.assert_testid(response, "yearbook-create-own")
    athe.assert_no_testid(response, "yearbook-edit-own")


@pytest.mark.django_db
def test_entry_list_offers_to_edit_an_existing_entry(
    athe: AtheClient,
    semester: Semester,
    student: Student,
    make_entry: Callable[..., YearbookEntry],
):
    entry = make_entry(student)

    response = athe.get_ok(list_url(semester))

    assert response.context["has_entry"] is True
    assert response.context["user_entry"] == entry
    athe.assert_testid(response, "yearbook-edit-own")
    athe.assert_no_testid(response, "yearbook-create-own")


@pytest.mark.django_db
def test_entry_list_closes_once_the_semester_has_ended(
    athe: AtheClient,
    past_semester_for_yearbook: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    user = make_user()
    make_student(past_semester_for_yearbook, user=user)

    athe.login(user)
    response = athe.get_ok(list_url(past_semester_for_yearbook))

    assert response.context["can_edit"] is False
    athe.assert_testid(response, "yearbook-closed")
    athe.assert_no_testid(response, "yearbook-create-own", "yearbook-edit-own")


@pytest.mark.django_db
def test_entry_list_cards_carry_the_social_links(
    athe: AtheClient,
    semester: Semester,
    student: Student,
    make_student: Callable[..., Student],
    make_entry: Callable[..., YearbookEntry],
):
    make_entry(
        make_student(semester, house=Student.House.BLOB),
        display_name="Social Person",
        discord_username="socialuser#1234",
        instagram_username="socialinsta",
        github_username="socialgit",
        website_url="https://social.example.com",
    )

    response = athe.get_ok(list_url(semester))

    for link in (
        b"socialuser#1234",
        b"instagram.com/socialinsta",
        b"github.com/socialgit",
        b"https://social.example.com",
    ):
        assert link in response.content
