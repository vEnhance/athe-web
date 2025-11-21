import logging
from datetime import timedelta
from typing import Any

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from courses.models import CourseMeeting

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send Discord reminders for upcoming course meetings within 24 hours"

    def handle(self, *args: Any, **options: Any) -> None:
        now = timezone.now()
        deadline = now + timedelta(hours=24)

        # Find meetings that are upcoming within 24 hours and no reminder sent
        upcoming_meetings = CourseMeeting.objects.filter(
            start_time__gte=now,
            start_time__lte=deadline,
            reminder_sent=False,
            course__discord_reminders_enabled=True,
        ).select_related("course")

        if not upcoming_meetings.exists():
            self.stdout.write(
                self.style.SUCCESS("No meetings require reminders at this time.")
            )
            return

        sent_count = 0
        error_count = 0

        for meeting in upcoming_meetings:
            course = meeting.course

            # Skip if no Discord webhook configured
            if not course.discord_webhook:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {meeting}: No Discord webhook configured"
                    )
                )
                continue

            # Prepare Discord message
            unix_timestamp = int(meeting.start_time.timestamp())
            role_mention = (
                f"<@&{course.discord_role_id}>" if course.discord_role_id else "@here"
            )

            # Build message content
            kind = "club" if course.is_club else "class"
            message_parts = [
                f"{role_mention} Reminder: the {kind} **{course.name}** is meeting soon!",
                f"Time: <t:{unix_timestamp}:F> --- <t:{unix_timestamp}:R>",
            ]
            if meeting.title:
                message_parts.append(f"Topic: {meeting.title}")
            if course.zoom_meeting_link:
                message_parts.append(f"Zoom link: {course.zoom_meeting_link}")
            message_parts.append(
                f"Full schedule: https://beta.athemath.org{course.get_absolute_url}"
            )

            message_content = "\n".join(message_parts)

            # Send to Discord webhook
            try:
                response = requests.post(
                    course.discord_webhook,
                    json={"content": message_content},
                    timeout=10,
                )
                response.raise_for_status()

                # Mark reminder as sent
                meeting.reminder_sent = True
                meeting.save(update_fields=["reminder_sent"])

                self.stdout.write(self.style.SUCCESS(f"Sent reminder for: {meeting}"))
                sent_count += 1

            except requests.exceptions.RequestException as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to send reminder for {meeting}: {e}")
                )
                logger.error(f"Discord webhook error for {meeting}: {e}")
                error_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Sent {sent_count} reminders, {error_count} errors")
        )
