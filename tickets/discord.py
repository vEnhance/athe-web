import logging
import os
from datetime import datetime
from typing import Any

import requests
from django.contrib.auth.models import User
from django.http import HttpRequest

from .models import Ticket

logger = logging.getLogger(__name__)

RESOLVED_COLOR = 0x2ECC71
UNRESOLVED_COLOR = 0xE74C3C

EMBED_DESCRIPTION_LIMIT = 4096
EMBED_FIELD_LIMIT = 1024


def discord_time(when: datetime) -> str:
    return f"<t:{int(when.timestamp())}:f>"


def truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def ticket_embed(ticket: Ticket, url: str) -> dict[str, Any]:
    where = ticket.destination
    if ticket.meeting is not None:
        where += f" on {discord_time(ticket.meeting.start_time)}"
    fields = [
        {"name": "Student", "value": str(ticket.student), "inline": True},
        {
            "name": "Discord",
            "value": ticket.discord_username or "unknown",
            "inline": True,
        },
        {"name": "Asked", "value": discord_time(ticket.created_at), "inline": True},
        {"name": "Where", "value": where, "inline": False},
    ]
    if ticket.resolved_at is not None:
        resolver = ticket.resolved_by
        name = "staff"
        if isinstance(resolver, User):
            name = resolver.get_full_name() or resolver.username
        fields.append(
            {
                "name": "Resolved",
                "value": f"By {name} on {discord_time(ticket.resolved_at)}",
                "inline": False,
            }
        )
    if ticket.staff_notes:
        fields.append(
            {
                "name": "Staff notes",
                "value": truncate(ticket.staff_notes, EMBED_FIELD_LIMIT),
                "inline": False,
            }
        )
    return {
        "title": ticket.title,
        "url": url,
        "description": truncate(ticket.question, EMBED_DESCRIPTION_LIMIT),
        "color": RESOLVED_COLOR if ticket.is_resolved else UNRESOLVED_COLOR,
        "fields": fields,
    }


def notify_ticket(request: HttpRequest, ticket: Ticket, event: str) -> None:
    """Post the ticket to DISCORD_TICKETS_WEBHOOK, if that is set."""
    webhook_url = os.environ.get("DISCORD_TICKETS_WEBHOOK")
    if not webhook_url:
        return
    url = request.build_absolute_uri(ticket.get_absolute_url())
    payload = {
        "content": f"Question {event}: <{url}>",
        "embeds": [ticket_embed(ticket, url)],
        "allowed_mentions": {"parse": []},
    }
    try:
        requests.post(webhook_url, json=payload, timeout=10).raise_for_status()
    except requests.exceptions.RequestException:
        logger.exception("Failed to send ticket %s to Discord", ticket.pk)
