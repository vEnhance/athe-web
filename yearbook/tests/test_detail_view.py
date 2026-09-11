from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student
from yearbook.models import YearbookEntry


def detail_url(entry: YearbookEntry) -> str:
    return reverse("yearbook:entry_detail", kwargs={"pk": entry.pk})


@pytest.fixture
def entry(
    semester: Semester,
    make_student: Callable[..., Student],
    make_entry: Callable[..., YearbookEntry],
) -> YearbookEntry:
    student = make_student(semester, house=Student.House.OWL, airtable_name="Owlet")
    return make_entry(student, display_name="Entry Person", bio="This is my bio")


@pytest.fixture
def viewer(
    athe: AtheClient,
    semester: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
) -> User:
    """Someone enrolled in the same semester, so allowed to read the entry."""
    user = make_user(username="viewer")
    make_student(semester, user=user)
    return athe.login(user)


@pytest.mark.django_db
def test_detail_view_requires_login(athe: AtheClient, entry: YearbookEntry):
    athe.get_redirects(reverse("login"), detail_url(entry))


@pytest.mark.django_db
def test_detail_view_staff_can_access_any_entry(
    athe: AtheClient, entry: YearbookEntry, make_user: Callable[..., User]
):
    athe.login(make_user(username="staff", is_staff=True))
    response = athe.get_ok(detail_url(entry))

    assert response.context["entry"] == entry


@pytest.mark.django_db
def test_detail_view_student_in_semester_can_access(
    athe: AtheClient, entry: YearbookEntry, viewer: User
):
    response = athe.get_ok(detail_url(entry))

    assert athe.text_of(response, "entry-name") == "Entry Person"
    assert athe.text_of(response, "entry-bio") == "This is my bio"


@pytest.mark.django_db
def test_detail_view_student_not_in_semester_denied(
    athe: AtheClient,
    entry: YearbookEntry,
    past_semester_for_yearbook: Semester,
    make_user: Callable[..., User],
    make_student: Callable[..., Student],
):
    user = make_user(username="outsider")
    make_student(past_semester_for_yearbook, user=user)

    athe.login(user)
    assert athe.get(detail_url(entry)).status_code == 403


@pytest.mark.django_db
def test_detail_view_user_without_student_denied(
    athe: AtheClient, entry: YearbookEntry, make_user: Callable[..., User]
):
    athe.login(make_user(username="regular"))
    assert athe.get(detail_url(entry)).status_code == 403


@pytest.mark.django_db
def test_detail_view_shows_full_bio(
    athe: AtheClient, entry: YearbookEntry, viewer: User
):
    """The listing card truncates; the detail page is where the whole bio lives."""
    entry.bio = "This is a very long biography. " * 20
    entry.save()

    response = athe.get_ok(detail_url(entry))

    assert athe.text_of(response, "entry-bio") == entry.bio.strip()


@pytest.mark.django_db
def test_detail_view_shows_social_links(
    athe: AtheClient, entry: YearbookEntry, viewer: User
):
    entry.discord_username = "socialuser#1234"
    entry.instagram_username = "socialinsta"
    entry.github_username = "socialgit"
    entry.website_url = "https://social.example.com"
    entry.save()

    response = athe.get_ok(detail_url(entry))

    socials = athe.text_of(response, "entry-socials")
    assert "socialuser#1234" in socials
    assert "socialinsta" in socials
    assert "socialgit" in socials
    assert "https://social.example.com" in socials


@pytest.mark.django_db
def test_detail_view_shows_house(athe: AtheClient, entry: YearbookEntry, viewer: User):
    response = athe.get_ok(detail_url(entry))

    assert athe.text_of(response, "entry-house") == "Owls"


@pytest.mark.django_db
def test_detail_view_has_back_link(
    athe: AtheClient, semester: Semester, entry: YearbookEntry, viewer: User
):
    response = athe.get_ok(detail_url(entry))

    athe.assert_testid(response, "entry-back")
    back = reverse("yearbook:entry_list", kwargs={"slug": semester.slug})
    assert f'href="{back}"'.encode() in response.content


@pytest.mark.django_db
def test_detail_view_nonexistent_entry_returns_404(
    athe: AtheClient, make_user: Callable[..., User]
):
    athe.login(make_user(username="staff", is_staff=True))
    url = reverse("yearbook:entry_detail", kwargs={"pk": 99999})
    assert athe.get(url).status_code == 404
