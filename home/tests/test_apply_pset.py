from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from home.models import ApplyPSet

APPLY = reverse("home:apply")
PAST_PSETS = reverse("home:past_psets")


@pytest.fixture
def make_pset() -> Callable[..., ApplyPSet]:
    def _make(name: str, status: str, days: int, **kwargs: Any) -> ApplyPSet:
        defaults = {
            "deadline": timezone.localdate() + timedelta(days=days),
            "instructions": f"Instructions for {name}.",
            "closed_message": f"{name} is closed.",
        }
        return ApplyPSet.objects.create(name=name, status=status, **(defaults | kwargs))

    return _make


@pytest.mark.django_db
def test_apply_pset_ordering(make_pset: Callable[..., ApplyPSet]):
    """The newest deadline comes first, so the default listing reads backwards."""
    first = make_pset("PSet 1", ApplyPSet.Status.ACTIVE, 10)
    second = make_pset("PSet 2", ApplyPSet.Status.ACTIVE, 20)

    assert list(ApplyPSet.objects.all()) == [second, first]


@pytest.mark.django_db
def test_apply_pset_str(make_pset: Callable[..., ApplyPSet]):
    assert str(make_pset("Test PSet", ApplyPSet.Status.DRAFT, 0)) == "Test PSet"


@pytest.mark.django_db
def test_apply_view_with_active_psets(
    athe: AtheClient, make_pset: Callable[..., ApplyPSet]
):
    pset = make_pset(
        "Active PSet",
        ApplyPSet.Status.ACTIVE,
        30,
        instructions="These are the instructions.",
    )

    response = athe.get_ok(APPLY)

    assert list(response.context["active_psets"]) == [pset]
    assert "These are the instructions." in athe.text_of(response, "apply-pset")


@pytest.mark.django_db
def test_apply_view_with_no_active_shows_closed_message(
    athe: AtheClient, make_pset: Callable[..., ApplyPSet]
):
    pset = make_pset(
        "Completed PSet",
        ApplyPSet.Status.COMPLETED,
        -10,
        closed_message="Applications are closed for now.",
    )

    response = athe.get_ok(APPLY)

    assert response.context["most_recent_pset"] == pset
    assert "Applications are closed for now." in athe.text_of(
        response, "apply-closed-message"
    )


@pytest.mark.django_db
def test_apply_view_with_no_psets_at_all(athe: AtheClient):
    response = athe.get_ok(APPLY)

    athe.assert_testid(response, "apply-nothing-yet")


@pytest.mark.django_db
def test_apply_view_does_not_show_draft_psets(
    athe: AtheClient, make_pset: Callable[..., ApplyPSet]
):
    make_pset("Draft PSet", ApplyPSet.Status.DRAFT, 30)

    response = athe.get_ok(APPLY)

    athe.assert_no_testid(response, "apply-pset")
    athe.assert_testid(response, "apply-nothing-yet")


@pytest.mark.django_db
def test_apply_view_shows_multiple_active_psets(
    athe: AtheClient, make_pset: Callable[..., ApplyPSet]
):
    first = make_pset("Active PSet 1", ApplyPSet.Status.ACTIVE, 20)
    second = make_pset("Active PSet 2", ApplyPSet.Status.ACTIVE, 30)

    response = athe.get_ok(APPLY)

    assert list(response.context["active_psets"]) == [second, first]
    athe.assert_testid_count(response, "apply-pset", 2)


@pytest.mark.django_db
def test_apply_view_shows_most_recent_completed_message(
    athe: AtheClient, make_pset: Callable[..., ApplyPSet]
):
    make_pset("Old PSet", ApplyPSet.Status.COMPLETED, -60)
    recent = make_pset("Recent PSet", ApplyPSet.Status.COMPLETED, -10)

    response = athe.get_ok(APPLY)

    assert response.context["most_recent_pset"] == recent


@pytest.mark.django_db
def test_past_psets_view_shows_only_completed_psets(
    athe: AtheClient, make_pset: Callable[..., ApplyPSet]
):
    completed = make_pset("Completed PSet", ApplyPSet.Status.COMPLETED, -30)
    make_pset("Active PSet", ApplyPSet.Status.ACTIVE, 30)
    make_pset("Draft PSet", ApplyPSet.Status.DRAFT, 15)

    response = athe.get_ok(PAST_PSETS)

    assert list(response.context["psets"]) == [completed]


@pytest.mark.django_db
def test_past_psets_view_with_no_completed_psets(athe: AtheClient):
    response = athe.get_ok(PAST_PSETS)

    assert list(response.context["psets"]) == []
    athe.assert_testid(response, "past-psets-empty")


@pytest.mark.django_db
def test_past_psets_view_reverse_chronological_order(
    athe: AtheClient, make_pset: Callable[..., ApplyPSet]
):
    make_pset("Old PSet", ApplyPSet.Status.COMPLETED, -60)
    make_pset("Recent PSet", ApplyPSet.Status.COMPLETED, -10)

    response = athe.get_ok(PAST_PSETS)

    assert athe.texts_of(response, "past-pset") == ["Recent PSet", "Old PSet"]
