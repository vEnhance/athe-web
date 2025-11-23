import pytest
from django.urls import reverse
from django.test import Client


@pytest.mark.django_db
def test_login_works():
    client = Client()
    response = client.get(reverse("account_login"))
    assert response.status_code == 200
