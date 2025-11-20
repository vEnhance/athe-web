from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from courses.models import Semester, Student


class Award(models.Model):
    """Tracks house points earned by students or awarded directly to houses."""

    class AwardType(models.TextChoices):
        INTRO_POST = "intro_post", "Introduction Post"
        CLASS_ATTENDANCE = "class_attendance", "Class Attendance"
        HOMEWORK = "homework", "Homework Submission"
        EVENT = "event", "Club/Seminar/Event Attendance"
        OFFICE_HOURS = "office_hours", "Office Hours"
        POTD_TOP3 = "potd_top3", "PotD Top 3"
        POTD_4_10 = "potd_4_10", "PotD Place 4-10"
        STAFF_BONUS = "staff_bonus", "Staff Bonus"
        HOUSE_ACTIVITY = "house_activity", "House Activity Bonus"
        OTHER = "other", "Other"

    # Default point values for each award type
    DEFAULT_POINTS = {
        "intro_post": 1,
        "class_attendance": 5,
        "homework": 5,
        "event": 3,
        "office_hours": 2,
        "potd_top3": 20,
        "potd_4_10": 10,
        "staff_bonus": 2,
        "house_activity": 50,
        "other": 0,
    }

    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="awards"
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name="awards",
        null=True,
        blank=True,
        help_text="Student receiving the award. Leave blank for house-level awards.",
    )
    house = models.CharField(
        max_length=20,
        choices=Student.House.choices,
        blank=True,
        help_text="For house-level awards only. Auto-filled from student if applicable.",
    )
    award_type = models.CharField(
        max_length=30,
        choices=AwardType.choices,
        help_text="Type of activity that earned these points.",
    )
    points = models.IntegerField(help_text="Number of points awarded.")
    description = models.TextField(
        blank=True, help_text="Optional description or notes about this award."
    )
    awarded_at = models.DateTimeField(
        default=timezone.now, help_text="When this award was given."
    )
    awarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="awards_given",
        help_text="Staff member who awarded these points.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        if self.student:
            return (
                f"{self.student.user.username} - {self.get_award_type_display()} "  # type: ignore[attr-defined]
                f"({self.points} pts)"
            )
        else:
            return (
                f"{self.get_house_display()} - {self.get_award_type_display()} "  # type: ignore[attr-defined]
                f"({self.points} pts)"
            )

    def clean(self) -> None:
        """Validate the award."""
        super().clean()

        # If student is set, auto-fill house from student
        if self.student:
            if not self.student.house:
                raise ValidationError(
                    "Cannot award points to a student without a house assignment."
                )
            # Auto-set house from student
            if not self.house:
                self.house = self.student.house
            elif self.house != self.student.house:
                raise ValidationError(
                    f"House mismatch: student is in {self.student.get_house_display()} "  # type: ignore[attr-defined]
                    f"but award is for {self.get_house_display()}."  # type: ignore[attr-defined]
                )
            # Ensure student belongs to the same semester
            if self.student.semester != self.semester:
                raise ValidationError(
                    f"Student {self.student} is not enrolled in {self.semester}."
                )
        else:
            # House-level award must have house set
            if not self.house:
                raise ValidationError("House-level awards must specify a house.")

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        # Auto-fill house from student before saving
        if self.student and self.student.house:
            self.house = self.student.house
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ("-awarded_at",)
        indexes = [
            models.Index(fields=["semester", "house"]),
            models.Index(fields=["semester", "student"]),
            models.Index(fields=["awarded_at"]),
        ]
