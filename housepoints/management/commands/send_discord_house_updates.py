import os
from typing import Any

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from courses.models import Semester
from housepoints.models import Award

# Discord emoji mappings for each house
HOUSE_EMOJIS: dict[str, str] = {
    "owl": "<:owlheart:1457263992245326022>",
    "blob": "<:blobheart:822453188853760071>",
    "red_panda": "<:redpandaheart:1227043341686804510>",
    "cat": "<:catlove:1301819346888429618>",
    "bunny": "<:bunnylove:1324915395035005089>",
}


# Discord role ID for house points updates
HOUSE_POINTS_ROLE_ID = "1345991464831811665"


class Command(BaseCommand):
    help = "Send Discord updates with current house points standings"

    def handle(self, *args: Any, **options: Any) -> None:
        # Check for webhook environment variable
        webhook_url = os.environ.get("DISCORD_HOUSE_POINTS_WEBHOOK")
        if not webhook_url:
            self.stderr.write(
                self.style.ERROR(
                    "DISCORD_HOUSE_POINTS_WEBHOOK environment variable is not set"
                )
            )
            raise SystemExit(1)

        # Get the currently active semester
        try:
            semester = Semester.objects.active().get()
        except Semester.DoesNotExist:
            self.stderr.write(
                self.style.ERROR("No active semester found for the current date")
            )
            return
        except Semester.MultipleObjectsReturned:
            self.stderr.write(
                self.style.ERROR(
                    "Multiple active semesters found. "
                    "Please ensure semester dates do not overlap."
                )
            )
            raise SystemExit(1)

        # Check if leaderboard is frozen
        if semester.house_points_freeze_date is not None:
            self.stdout.write(
                self.style.WARNING(
                    f"Leaderboard is frozen as of {semester.house_points_freeze_date}. "
                    "No update sent."
                )
            )
            return

        # The freeze check above means this always reflects live standings
        house_scores = Award.objects.for_semester(semester).totals_by_house()
        sorted_houses = sorted(
            house_scores.items(),
            key=lambda item: (-item[1], item[0]),  # Secondary sort by name
        )

        # Build the message lines
        message_lines = [f"<@&{HOUSE_POINTS_ROLE_ID}> Current standings!"]
        for n, (house_code, points) in enumerate(sorted_houses, start=1):
            emoji = HOUSE_EMOJIS.get(house_code, "")
            message_lines.append(f"{n}. {emoji} {points} points")

        unix_timestamp = int(timezone.now().timestamp())
        message_lines.append("")  # Empty line before links
        message_lines.append(f"Generated at <t:{unix_timestamp}:F>")
        message_lines.append("_Live scoreboard_: https://athemath.org/house-points/")
        message_lines.append(
            "_Your awards_: https://athemath.org/house-points/awards/my/"
        )

        message_content = "\n".join(message_lines)

        # Send to Discord webhook
        try:
            response = requests.post(
                webhook_url,
                json={"content": message_content},
                timeout=10,
            )
            response.raise_for_status()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully sent house points update for {semester.name}"
                )
            )
        except requests.exceptions.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Failed to send Discord message: {e}"))
            raise SystemExit(1)
