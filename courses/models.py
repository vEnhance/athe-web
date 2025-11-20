from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from home.models import StaffPhotoListing


class Semester(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    start_date = models.DateField(help_text="When this semester starts")
    end_date = models.DateField(help_text="When this semester ends")
    house_points_freeze_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="If set, leaderboard shows only points awarded up to this date",
    )

    def __str__(self) -> str:
        return self.name

    def is_active(self) -> bool:
        """Check if the semester is currently active."""
        today = date.today()
        return self.start_date <= today <= self.end_date

    class Meta:
        ordering = ("-start_date",)


class Course(models.Model):
    name = models.CharField(max_length=200)
    is_club = models.BooleanField(
        default=False,
        help_text="Whether this is a club (vs. a class).",
    )
    description = models.TextField()
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="courses"
    )
    instructor = models.ForeignKey(
        StaffPhotoListing,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="courses",
        help_text="Link to the instructor for this course.",
    )
    leaders = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="led_courses",
        blank=True,
        help_text="Users who can manage this course and its meetings.",
    )
    difficulty = models.CharField(
        blank=True,
        max_length=80,
        help_text="Estimate of the difficulty of this course.",
    )
    lesson_plan = models.TextField(
        blank=True, help_text="List of lessons planned for this course. One per line."
    )
    regular_meeting_time = models.CharField(
        blank=True,
        max_length=200,
        help_text="Regular meeting time for this course, e.g. '5pm-6pm ET on Saturday'.",
    )
    google_classroom_direct_link = models.URLField(
        blank=True, help_text="Direct link to the Google Classroom for this course."
    )
    google_classroom_join_link = models.URLField(
        blank=True, help_text="Join link for students to join the Google Classroom."
    )
    zoom_meeting_link = models.URLField(
        blank=True, help_text="Zoom meeting link for this course."
    )
    discord_webhook = models.URLField(
        blank=True, help_text="Discord webhook URL for posting reminders."
    )
    discord_role_id = models.CharField(
        blank=True,
        max_length=100,
        help_text="Discord role ID to mention in reminders.",
    )
    discord_reminders_enabled = models.BooleanField(
        default=True, help_text="Whether to send Discord reminders."
    )

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ("-semester__start_date", "is_club", "name")


class Student(models.Model):
    class House(models.TextChoices):
        BLOB = "blob", "Blob"
        CAT = "cat", "Cat"
        OWL = "owl", "Owl"
        RED_PANDA = "red_panda", "Red Panda"
        BUNNY = "bunny", "Bunny"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="students"
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="students"
    )
    house = models.CharField(
        max_length=20,
        choices=House.choices,
        blank=True,
        help_text="House assignment for this semester",
    )
    enrolled_courses = models.ManyToManyField(
        Course, related_name="enrolled_students", blank=True
    )

    def __str__(self) -> str:
        return f"{self.user.username} ({self.semester})"

    def clean(self) -> None:
        """Validate that all enrolled courses belong to the student's semester."""
        super().clean()
        # Only validate if the instance has been saved (has a pk)
        if self.pk:
            wrong_semester_courses = self.enrolled_courses.exclude(
                semester=self.semester
            )
            if wrong_semester_courses.exists():
                course_names = ", ".join(
                    wrong_semester_courses.values_list("name", flat=True)
                )
                raise ValidationError(
                    f"The following courses are not in {self.semester}: {course_names}"
                )

    class Meta:
        unique_together = ("user", "semester")
        ordering = ("-semester__start_date", "user__username")


class CourseMeeting(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="meetings"
    )
    start_time = models.DateTimeField(help_text="When this meeting starts.")
    title = models.CharField(
        max_length=200, blank=True, help_text="Topic for this lecture."
    )
    reminder_sent = models.BooleanField(
        default=False, help_text="Whether a reminder has been sent for this meeting."
    )

    def __str__(self) -> str:
        return f"{self.course.name} - {self.title} ({self.start_time})"

    class Meta:
        ordering = ("start_time",)
