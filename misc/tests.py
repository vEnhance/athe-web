from django.urls import reverse
from django.test import Client


def test_login_works():
    client = Client()
    response = client.get(reverse("misc:sp26game"))
    assert response.status_code == 200
