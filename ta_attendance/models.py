from django.conf import settings
from django.db import models

from courses.models import Course


class Attendance(models.Model):
    """Record of a staff member's attendance at a club session."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ta_attendance_records",
    )
    date = models.DateField()
    club = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="ta_attendance_records",
        limit_choices_to={"is_club": True},
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date", "club"],
                name="unique_user_date_club",
            )
        ]
        ordering = ["-date", "club__name"]

    def __str__(self) -> str:
        return f"{self.user.get_full_name() or self.user.username} - {self.club.name} on {self.date}"
