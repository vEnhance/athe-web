from collections.abc import Callable
from urllib.parse import urlparse

import pytest
from django.contrib.admin import helpers
from django.contrib.auth.models import Permission, User
from django.test import Client
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student

pytestmark = pytest.mark.django_db

CHANGELIST = reverse("admin:auth_user_changelist")
ACTION = "make_password_reset_links"


def make_links(athe: AtheClient, *users: User) -> list[str]:
    response = athe.post(
        CHANGELIST,
        {"action": ACTION, helpers.ACTION_CHECKBOX_NAME: [u.pk for u in users]},
        follow=True,
    )
    return [
        urlparse(str(m).split(": ", 1)[1]).path for m in response.context["messages"]
    ]


def action_names(athe: AtheClient) -> list[str]:
    choices = athe.get_ok(CHANGELIST).context["action_form"].fields["action"].choices
    return [name for name, _ in choices]


def test_only_superusers_get_the_action(
    athe: AtheClient, make_user: Callable[..., User]
) -> None:
    staff = make_user("ta", is_staff=True)
    staff.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="auth", codename__endswith="_user"
        )
    )
    athe.login(staff)
    assert ACTION not in action_names(athe)

    athe.login(make_user("admin", is_superuser=True, is_staff=True))
    assert ACTION in action_names(athe)


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
    [path] = make_links(athe, forgetful)

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
