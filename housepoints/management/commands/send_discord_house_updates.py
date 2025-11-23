import os
from typing import Any

import requests
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from courses.models import Semester, Student
from housepoints.models import Award


# Discord emoji mappings for each house
HOUSE_EMOJIS: dict[str, str] = {
    "owl": "<:owlheart:1307684456982904943>",
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
        today = timezone.now().date()
        active_semesters = Semester.objects.filter(
            start_date__lte=today, end_date__gte=today
        )

        count = active_semesters.count()
        if count == 0:
            self.stderr.write(
                self.style.ERROR("No active semester found for the current date")
            )
            raise SystemExit(1)
        if count > 1:
            self.stderr.write(
                self.style.ERROR(
                    f"Multiple active semesters found ({count}). "
                    "Please ensure semester dates do not overlap."
                )
            )
            raise SystemExit(1)

        semester = active_semesters.get()

        # Check if leaderboard is frozen
        if semester.house_points_freeze_date is not None:
            self.stdout.write(
                self.style.WARNING(
                    f"Leaderboard is frozen as of {semester.house_points_freeze_date}. "
                    "No update sent."
                )
            )
            return

        # Calculate house totals
        awards_query = Award.objects.filter(semester=semester)
        house_totals = (
            awards_query.values("house")
            .annotate(total_points=Sum("points"))
            .order_by("-total_points")
        )

        # Build a dict of house -> points
        house_scores: dict[str, int] = {}
        for entry in house_totals:
            if entry["house"]:  # Skip empty house entries
                house_scores[entry["house"]] = entry["total_points"] or 0

        # Add houses with 0 points that aren't in the results
        for house_code, _ in Student.House.choices:
            if house_code not in house_scores:
                house_scores[house_code] = 0

        # Sort by points descending
        sorted_houses = sorted(
            house_scores.items(),
            key=lambda x: (-x[1], x[0]),  # Secondary sort by name
        )

        # Build the message lines
        message_lines = [f"<@&{HOUSE_POINTS_ROLE_ID}> Current standings!"]
        n = 0
        for house_code, points in sorted_houses:
            n += 1
            emoji = HOUSE_EMOJIS.get(house_code, "")
            message_lines.append(f"{n}. {emoji} {points} points")

        unix_timestamp = int(timezone.now().timestamp())
        message_lines.append("")  # Empty line before links
        message_lines.append(f"Generated at <t:{unix_timestamp}:F>")
        message_lines.append(
            "_Live scoreboard_: https://beta.athemath.org/house-points/"
        )
        message_lines.append(
            "_Your awards_: https://beta.athemath.org/house-points/awards/my/"
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
