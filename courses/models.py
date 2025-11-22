from datetime import date

from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef
from django.db.models import UniqueConstraint, Q, QuerySet
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
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
    house_points_class_threshold = models.PositiveIntegerField(
        default=14,
        help_text="Number of class attendances worth 5 points; subsequent are worth 3",
    )
    visible = models.BooleanField(
        default=True,
        help_text="If unchecked, this semester will be hidden from non-staff users",
    )

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("courses:course_list", kwargs={"slug": self.slug})

    def is_active(self) -> bool:
        """Check if the semester is currently active."""
        today = date.today()
        return self.start_date <= today <= self.end_date

    @classmethod
    def get_enrolled_semesters(cls, user: User) -> QuerySet["Semester"]:
        return Semester.objects.filter(
            Exists(Student.objects.filter(semester=OuterRef("pk"), user=user))
        )

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
    students = models.ManyToManyField(
        "Student",
        related_name="enrolled_courses",
        blank=True,
        help_text="Students enrolled in this course.",
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
        default=False, help_text="Whether to send Discord reminders."
    )

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("courses:course_detail", kwargs={"pk": self.pk})

    def save(self, *args, **kwargs) -> None:  # type: ignore[override]
        """Override save to auto-add instructor as a leader."""
        super().save(*args, **kwargs)
        # Add instructor's user as a leader if instructor is set and has a user
        if self.instructor and self.instructor.user:
            self.leaders.add(self.instructor.user)

    def clean(self) -> None:
        """Validate that all students belong to the course's semester."""
        super().clean()
        # Only validate if the instance has been saved (has a pk)
        if self.pk:
            wrong_semester_students = self.students.exclude(semester=self.semester)
            if wrong_semester_students.exists():
                student_names = ", ".join(
                    str(student) for student in wrong_semester_students
                )
                raise ValidationError(
                    f"The following students are not in {self.semester}: {student_names}"
                )

    class Meta:
        ordering = ("-semester__start_date", "is_club", "name")


class Student(models.Model):
    class House(models.TextChoices):
        BLOB = "blob", "Blobs"
        CAT = "cat", "Cats"
        OWL = "owl", "Owls"
        RED_PANDA = "red_panda", "Red Panda"
        BUNNY = "bunny", "Bunnies"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
    )
    airtable_name = models.CharField(
        max_length=80,
        help_text="A unique name for the student, as listed in Airtable. "
        "This is used to disambiguate students during the registration process "
        "and when awarding house points, but generally doesn't appear to students.",
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

    def __str__(self) -> str:
        if self.user is not None and (full_name := self.user.get_full_name()):
            return full_name
        else:
            return self.airtable_name

    class Meta:
        constraints = (
            UniqueConstraint(
                fields=["user", "semester"],
                condition=Q(user__isnull=False),
                name="unique_user_per_semester",
            ),
            UniqueConstraint(
                fields=["airtable_name", "semester"],
                name="unique_airtable_name_per_semester",
            ),
        )
        ordering = ("-semester__start_date", "airtable_name")


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
