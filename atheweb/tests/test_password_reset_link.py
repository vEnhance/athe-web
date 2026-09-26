from collections.abc import Callable
from urllib.parse import urlparse

import pytest
from django.contrib.auth.models import Permission, User
from django.test import Client
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student

pytestmark = pytest.mark.django_db

CHANGELIST = reverse("admin:auth_user_changelist")


def reset_link_url(user: User) -> str:
    return reverse("admin:auth_user_reset_link", args=[user.pk])


def test_only_superusers_can_make_links(
    athe: AtheClient, make_user: Callable[..., User]
) -> None:
    forgetful = make_user("forgetful")
    change_page = reverse("admin:auth_user_change", args=[forgetful.pk])
    staff = make_user("ta", is_staff=True)
    staff.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="auth", codename__endswith="_user"
        )
    )
    athe.login(staff)
    athe.assert_no_testid(athe.get_ok(change_page), "reset-link-button")
    assert athe.get(reset_link_url(forgetful)).status_code == 403

    athe.login(make_user("admin", is_superuser=True, is_staff=True))
    athe.assert_testid(athe.get_ok(change_page), "reset-link-button")


def test_search_finds_a_user_by_their_roster_name(
    athe: AtheClient,
    make_user: Callable[..., User],
    semester: Semester,
    make_student: Callable[..., Student],
) -> None:
    forgetful = make_user("xX_gauss_Xx")
    make_student(semester, forgetful, airtable_name="Carl Gauss")
    make_user("euler")
    athe.login(make_user("admin", is_superuser=True, is_staff=True))

    response = athe.get_ok(CHANGELIST, data={"q": "carl gauss"})

    assert list(response.context["cl"].result_list) == [forgetful]


def test_the_link_lets_the_student_set_a_new_password_once(
    athe: AtheClient, make_user: Callable[..., User]
) -> None:
    forgetful = make_user("forgetful")
    athe.login(make_user("admin", is_superuser=True, is_staff=True))
    response = athe.get(reset_link_url(forgetful), follow=True)
    assert response.redirect_chain[-1][0] == reverse(
        "admin:auth_user_change", args=[forgetful.pk]
    )
    [message] = response.context["messages"]
    path = urlparse(str(message).split(": ", 1)[1]).path

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
