from django.contrib.auth.models import User
import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
def test_admin_requires_superuser():
    client = Client()
    url = reverse("home:manual")
    resp = client.get(url)
    assert resp.status_code == 302
    assert "Hello, my lovely" not in resp.content.decode()

    User.objects.create_user(username="scrub", password="password")
    client.login(username="scrub", password="password")
    resp = client.get(url)
    assert resp.status_code == 403
    assert "Hello, my lovely" not in resp.content.decode()

    User.objects.create_user(
        username="staff",
        password="password",
        is_staff=True,
    )
    client.login(username="staff", password="password")
    resp = client.get(url)
    assert resp.status_code == 403
    assert "Hello, my lovely" not in resp.content.decode()

    User.objects.create_user(
        username="evan",
        password="343768336d3437682e307267",
        is_superuser=True,
    )
    client.login(
        username="evan",
        password="343768336d3437682e307267",
        first_name="Evan",
        last_name="Chen",
    )
    resp = client.get(url)
    assert resp.status_code == 200
    assert "Hello, my lovely Evan" not in resp.content.decode()
