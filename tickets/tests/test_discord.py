from collections.abc import Callable, Iterator
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.contrib.auth.models import User
from django.urls import reverse

from atheweb.testsuite import AtheClient
from courses.models import CourseMeeting, Student
from tickets.discord import RESOLVED_COLOR, UNRESOLVED_COLOR
from tickets.models import Ticket

WEBHOOK = "https://discord.com/api/webhooks/1/abc"


@pytest.fixture
def post() -> Iterator[MagicMock]:
    with (
        patch.dict("os.environ", {"DISCORD_TICKETS_WEBHOOK": WEBHOOK}),
        patch("tickets.discord.requests.post") as post,
    ):
        yield post


def sent_embed(post: MagicMock) -> dict:
    post.assert_called_once()
    assert post.call_args.args[0] == WEBHOOK
    return post.call_args.kwargs["json"]["embeds"][0]


@pytest.mark.django_db
def test_submitting_posts_red_embed(
    athe: AtheClient, student: Student, sitting: CourseMeeting, post: MagicMock
):
    athe.login("lucy")
    athe.post_redirects(
        reverse("tickets:ticket_list"),
        reverse("tickets:submit"),
        {"title": "FLT", "question": "How do I start?", "meeting": sitting.pk},
    )

    ticket = Ticket.objects.get()
    embed = sent_embed(post)
    assert embed["color"] == UNRESOLVED_COLOR
    assert embed["title"] == "FLT"
    assert embed["description"] == "How do I start?"
    assert embed["url"] == f"http://testserver/tickets/review/{ticket.pk}/"


@pytest.mark.django_db
def test_posts_only_when_resolution_changes(
    athe: AtheClient,
    student: Student,
    staffer: User,
    make_ticket: Callable[..., Ticket],
    post: MagicMock,
):
    ticket = make_ticket(student)
    url = reverse("tickets:review_detail", kwargs={"pk": ticket.pk})
    review = reverse("tickets:review_list")
    athe.login(staffer)

    athe.post_redirects(review, url, {"resolved": "on"})
    assert sent_embed(post)["color"] == RESOLVED_COLOR
    assert post.call_args.kwargs["json"]["content"].startswith("Question resolved")

    post.reset_mock()
    athe.post_redirects(review, url, {"resolved": "on", "staff_notes": "Hi"})
    post.assert_not_called()

    athe.post_redirects(review, url, {"staff_notes": "Hi"})
    assert sent_embed(post)["color"] == UNRESOLVED_COLOR
    assert post.call_args.kwargs["json"]["content"].startswith("Question reopened")

    post.reset_mock()
    athe.post_redirects(review, url, {"staff_notes": "Still open"})
    post.assert_not_called()


@pytest.mark.django_db
def test_no_webhook_sends_nothing(
    athe: AtheClient, student: Student, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.delenv("DISCORD_TICKETS_WEBHOOK", raising=False)
    with patch("tickets.discord.requests.post") as post:
        athe.login("lucy")
        athe.post_redirects(
            reverse("tickets:ticket_list"),
            reverse("tickets:submit"),
            {"title": "FLT", "question": "?"},
        )
    post.assert_not_called()
    assert Ticket.objects.count() == 1


@pytest.mark.django_db
def test_webhook_failure_still_saves(
    athe: AtheClient, student: Student, post: MagicMock
):
    post.side_effect = requests.exceptions.ConnectionError
    athe.login("lucy")
    athe.post_redirects(
        reverse("tickets:ticket_list"),
        reverse("tickets:submit"),
        {"title": "FLT", "question": "?"},
    )
    assert Ticket.objects.count() == 1
