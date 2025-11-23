from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from home.models import ApplyPSet


@pytest.mark.django_db
def test_create_apply_pset():
    """Test creating an ApplyPSet."""
    pset = ApplyPSet.objects.create(
        name="Fall 2025 PSet",
        deadline=timezone.now() + timedelta(days=30),
        status="active",
        instructions="Apply by filling out the form.",
        closed_message="Applications closed!",
    )
    assert pset.name == "Fall 2025 PSet"
    assert pset.status == "active"


@pytest.mark.django_db
def test_apply_pset_ordering():
    """Test that ApplyPSets are ordered by deadline descending."""
    _pset1 = ApplyPSet.objects.create(
        name="PSet 1",
        deadline=timezone.now() + timedelta(days=10),
        status="active",
        instructions="Test",
        closed_message="Closed",
    )
    _pset2 = ApplyPSet.objects.create(
        name="PSet 2",
        deadline=timezone.now() + timedelta(days=20),
        status="active",
        instructions="Test",
        closed_message="Closed",
    )
    psets = list(ApplyPSet.objects.all())
    assert psets[0].name == "PSet 2"
    assert psets[1].name == "PSet 1"


@pytest.mark.django_db
def test_apply_pset_str():
    """Test the string representation of ApplyPSet."""
    pset = ApplyPSet.objects.create(
        name="Test PSet",
        deadline=timezone.now(),
        status="draft",
        instructions="Test",
        closed_message="Closed",
    )
    assert str(pset) == "Test PSet"


@pytest.mark.django_db
def test_apply_view_with_active_psets():
    """Test ApplyView displays active problem sets."""
    client = Client()
    _pset = ApplyPSet.objects.create(
        name="Active PSet",
        deadline=timezone.now() + timedelta(days=30),
        status="active",
        instructions="These are the instructions.",
        closed_message="Closed",
    )
    response = client.get(reverse("home:apply"))
    assert response.status_code == 200
    assert "Active PSet" in response.content.decode()
    assert "These are the instructions." in response.content.decode()


@pytest.mark.django_db
def test_apply_view_with_no_active_shows_closed_message():
    """Test ApplyView shows closed message when no active psets."""
    client = Client()
    _pset = ApplyPSet.objects.create(
        name="Completed PSet",
        deadline=timezone.now() - timedelta(days=10),
        status="completed",
        instructions="Instructions",
        closed_message="Applications are closed for now.",
    )
    response = client.get(reverse("home:apply"))
    assert response.status_code == 200
    assert "Applications are closed for now." in response.content.decode()


@pytest.mark.django_db
def test_apply_view_with_no_psets_at_all():
    """Test ApplyView shows generic message when no psets exist."""
    client = Client()
    response = client.get(reverse("home:apply"))
    assert response.status_code == 200
    assert "Nothing here yet, check back later!" in response.content.decode()


@pytest.mark.django_db
def test_apply_view_does_not_show_draft_psets():
    """Test ApplyView does not display draft problem sets."""
    client = Client()
    _pset = ApplyPSet.objects.create(
        name="Draft PSet",
        deadline=timezone.now() + timedelta(days=30),
        status="draft",
        instructions="Draft instructions",
        closed_message="Closed",
    )
    response = client.get(reverse("home:apply"))
    assert response.status_code == 200
    assert "Draft PSet" not in response.content.decode()
    assert "Nothing here yet, check back later!" in response.content.decode()


@pytest.mark.django_db
def test_apply_view_shows_multiple_active_psets():
    """Test ApplyView displays all active problem sets."""
    client = Client()
    _pset1 = ApplyPSet.objects.create(
        name="Active PSet 1",
        deadline=timezone.now() + timedelta(days=20),
        status="active",
        instructions="Instructions 1",
        closed_message="Closed",
    )
    _pset2 = ApplyPSet.objects.create(
        name="Active PSet 2",
        deadline=timezone.now() + timedelta(days=30),
        status="active",
        instructions="Instructions 2",
        closed_message="Closed",
    )
    response = client.get(reverse("home:apply"))
    assert response.status_code == 200
    assert "Active PSet 1" in response.content.decode()
    assert "Active PSet 2" in response.content.decode()


@pytest.mark.django_db
def test_apply_view_shows_most_recent_completed_message():
    """Test ApplyView shows closed message from most recent completed pset."""
    client = Client()
    _old_pset = ApplyPSet.objects.create(
        name="Old PSet",
        deadline=timezone.now() - timedelta(days=60),
        status="completed",
        instructions="Old instructions",
        closed_message="Old closed message",
    )
    _recent_pset = ApplyPSet.objects.create(
        name="Recent PSet",
        deadline=timezone.now() - timedelta(days=10),
        status="completed",
        instructions="Recent instructions",
        closed_message="Recent closed message",
    )
    response = client.get(reverse("home:apply"))
    assert response.status_code == 200
    assert "Recent closed message" in response.content.decode()
    assert "Old closed message" not in response.content.decode()


@pytest.mark.django_db
def test_past_psets_view_shows_completed_psets():
    """Test PastPsetsView displays completed problem sets."""
    client = Client()
    _pset = ApplyPSet.objects.create(
        name="Completed PSet",
        deadline=timezone.now() - timedelta(days=30),
        status="completed",
        instructions="Instructions",
        closed_message="Closed",
    )
    response = client.get(reverse("home:past_psets"))
    assert response.status_code == 200
    assert "Completed PSet" in response.content.decode()


@pytest.mark.django_db
def test_past_psets_view_does_not_show_active_psets():
    """Test PastPsetsView does not display active problem sets."""
    client = Client()
    _pset = ApplyPSet.objects.create(
        name="Active PSet",
        deadline=timezone.now() + timedelta(days=30),
        status="active",
        instructions="Instructions",
        closed_message="Closed",
    )
    response = client.get(reverse("home:past_psets"))
    assert response.status_code == 200
    assert "Active PSet" not in response.content.decode()


@pytest.mark.django_db
def test_past_psets_view_does_not_show_draft_psets():
    """Test PastPsetsView does not display draft problem sets."""
    client = Client()
    _pset = ApplyPSet.objects.create(
        name="Draft PSet",
        deadline=timezone.now() + timedelta(days=30),
        status="draft",
        instructions="Instructions",
        closed_message="Closed",
    )
    response = client.get(reverse("home:past_psets"))
    assert response.status_code == 200
    assert "Draft PSet" not in response.content.decode()


@pytest.mark.django_db
def test_past_psets_view_with_no_completed_psets():
    """Test PastPsetsView shows message when no completed psets exist."""
    client = Client()
    response = client.get(reverse("home:past_psets"))
    assert response.status_code == 200
    assert "No past problem sets available yet." in response.content.decode()


@pytest.mark.django_db
def test_past_psets_view_reverse_chronological_order():
    """Test PastPsetsView lists psets in reverse chronological order."""
    client = Client()
    _pset1 = ApplyPSet.objects.create(
        name="Old PSet",
        deadline=timezone.now() - timedelta(days=60),
        status="completed",
        instructions="Old",
        closed_message="Closed",
    )
    _pset2 = ApplyPSet.objects.create(
        name="Recent PSet",
        deadline=timezone.now() - timedelta(days=10),
        status="completed",
        instructions="Recent",
        closed_message="Closed",
    )
    response = client.get(reverse("home:past_psets"))
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    recent_pos = content.find("Recent PSet")
    old_pos = content.find("Old PSet")
    assert recent_pos < old_pos, "Recent PSet should appear before Old PSet"
