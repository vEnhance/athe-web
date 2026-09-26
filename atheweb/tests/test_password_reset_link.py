from collections.abc import Callable
from urllib.parse import urlparse

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student

pytestmark = pytest.mark.django_db

URL = reverse("password-reset-link")


@pytest.fixture
def admin(make_user: Callable[..., User]) -> User:
    return make_user("admin", is_superuser=True, is_staff=True)


def test_staff_who_are_not_superusers_are_turned_away(
    athe: AtheClient, make_user: Callable[..., User]
) -> None:
    athe.login(make_user("ta", is_staff=True))
    athe.get_redirects(reverse("index"), URL)
    athe.post_redirects(reverse("index"), URL, {"user": 1})


def test_search_finds_a_student_by_their_roster_name(
    athe: AtheClient,
    admin: User,
    make_user: Callable[..., User],
    semester: Semester,
    make_student: Callable[..., Student],
) -> None:
    forgetful = make_user("xX_gauss_Xx")
    make_student(semester, forgetful, airtable_name="Carl Gauss")
    make_user("euler")
    athe.login(admin)

    response = athe.get_ok(URL, data={"q": "gauss"})

    assert list(response.context["users"]) == [forgetful]
    assert athe.texts_of(response, "reset-username") == ["xX_gauss_Xx"]


def test_search_with_no_match_says_so(athe: AtheClient, admin: User) -> None:
    athe.login(admin)
    response = athe.get_ok(URL, data={"q": "nobody"})
    athe.assert_testid(response, "reset-no-match")


def test_the_link_lets_the_student_set_a_new_password_once(
    athe: AtheClient, admin: User, make_user: Callable[..., User]
) -> None:
    forgetful = make_user("forgetful")
    athe.login(admin)

    response = athe.post_ok(URL, {"user": forgetful.pk})
    assert response.context["target"] == forgetful
    path = urlparse(response.context["link"]).path

    student = Client()
    form_page = student.get(path, follow=True)
    assert form_page.context["form"].user == forgetful
    student.post(
        form_page.redirect_chain[-1][0],
        {"password1": "a-brand-new-pw", "password2": "a-brand-new-pw"},
    )

    forgetful.refresh_from_db()
    assert forgetful.check_password("a-brand-new-pw")
    assert Client().get(path).context["token_fail"]
