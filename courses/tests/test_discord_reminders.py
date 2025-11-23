from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from courses.management.commands.send_discord_reminders import Command
from courses.models import Course, CourseMeeting, Semester


@pytest.mark.django_db
@patch("requests.post")
def test_discord_reminder_command(mock_post):
    """Test the Discord reminder management command."""
    # Mock successful Discord API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=fall,
        discord_webhook="https://discord.com/api/webhooks/test",
        discord_role_id="123456",
        discord_reminders_enabled=True,
        zoom_meeting_link="https://zoom.us/j/test",
    )
    # Create a meeting within 24 hours
    meeting = CourseMeeting.objects.create(
        course=course,
        start_time=timezone.now() + timedelta(hours=12),
        title="Test Meeting",
    )

    # Run the command
    command = Command()
    out = StringIO()
    command.stdout = out
    command.handle()

    # Check that Discord API was called
    assert mock_post.called
    call_args = mock_post.call_args
    assert course.discord_webhook in call_args[0]
    assert "Test Meeting" in call_args[1]["json"]["content"]

    # Check that meeting was marked as sent
    meeting.refresh_from_db()
    assert meeting.reminder_sent is True


@pytest.mark.django_db
def test_discord_reminder_command_no_webhook():
    """Test that command skips meetings without webhook."""
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course", description="Test", semester=fall
    )
    meeting = CourseMeeting.objects.create(
        course=course,
        start_time=timezone.now() + timedelta(hours=12),
        title="Test Meeting",
    )

    command = Command()
    out = StringIO()
    command.stdout = out
    command.handle()

    # Meeting should not be marked as sent
    meeting.refresh_from_db()
    assert meeting.reminder_sent is False
