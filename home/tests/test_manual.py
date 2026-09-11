from collections.abc import Callable

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient

MANUAL = reverse("home:manual")
#: A line only the manual carries, so its absence means the page did not render.
GREETING = b"Hello, my lovely"


@pytest.mark.django_db
def test_manual_requires_superuser(athe: AtheClient, make_user: Callable[..., User]):
    assert GREETING not in athe.get(MANUAL).content

    athe.login(make_user(username="scrub"))
    response = athe.get(MANUAL)
    assert response.status_code == 403
    assert GREETING not in response.content

    athe.login(make_user(username="staff", is_staff=True))
    response = athe.get(MANUAL)
    assert response.status_code == 403
    assert GREETING not in response.content


@pytest.mark.django_db
def test_manual_greets_the_superuser_by_name(
    athe: AtheClient, make_user: Callable[..., User]
):
    athe.login(make_user(username="evan", is_superuser=True, first_name="Evan"))
    response = athe.get_ok(MANUAL)

    assert athe.text_of(response, "manual-greeting") == "Hello, my lovely Evan!"
