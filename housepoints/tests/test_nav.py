import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


# ============================================================================
# Navigation Tests
# ============================================================================


@pytest.mark.django_db
def test_navigation_links_for_authenticated_user():
    """Test that house points links appear in navigation for logged-in users."""
    client = Client()
    User.objects.create_user(username="user", password="password")

    client.login(username="user", password="password")
    url = reverse("home:index")
    response = client.get(url)

    content = response.content.decode()
    assert "House Standings" in content
    assert "My Awards" in content


@pytest.mark.django_db
def test_navigation_bulk_award_link_for_staff():
    """Test that Award Points link appears for staff only."""
    client = Client()
    User.objects.create_user(username="user", password="password")
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Regular user should not see Award Points link
    client.login(username="user", password="password")
    response = client.get(reverse("home:index"))
    content = response.content.decode()
    assert "Award Points" not in content

    # Staff should see Award Points link
    client.login(username="staff", password="password")
    response = client.get(reverse("home:index"))
    content = response.content.decode()
    assert "Award Points" in content
