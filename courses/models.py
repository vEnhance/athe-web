import secrets
from typing import ClassVar

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Exists, OuterRef, Q, QuerySet, UniqueConstraint
from django.urls import reverse
from django.utils import timezone

from home.models import StaffPhotoListing


class SemesterQuerySet(models.QuerySet["Semester"]):
    def visible_to(self, user: AbstractBaseUser | AnonymousUser) -> SemesterQuerySet:
        """Restrict to semesters this user is allowed to see."""
        if getattr(user, "is_staff", False):
            return self
        return self.filter(visible=True)

    def active(self) -> SemesterQuerySet:
        """Semesters that today falls inside of."""
        today = timezone.now().date()
        return self.filter(start_date__lte=today, end_date__gte=today)


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
    president_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Name of the student president running this semester. Shown to "
        "students on the dashboard while they wait on class and house assignments.",
    )

    objects: ClassVar[SemesterQuerySet] = SemesterQuerySet.as_manager()  # type: ignore[assignment]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return reverse("courses:course_list", kwargs={"slug": self.slug})

    def is_active(self) -> bool:
        """Check if the semester is currently active."""
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    @classmethod
    def get_enrolled_semesters(cls, user: User) -> QuerySet[Semester]:
        return Semester.objects.filter(
            Exists(Student.objects.filter(semester=OuterRef("pk"), user=user))
        )

    @classmethod
    def get_current_semester(cls) -> Semester:
        """Get the current active semester based on today's date.

        Returns the semester where today's date falls between start_date and end_date.

        Raises:
            ValueError: If no active semester is found or multiple overlapping semesters exist.
        """
        current_semesters = cls.objects.active()

        count = current_semesters.count()
        if count == 0:
            raise ValueError("No active semester found for the current date.")
        if count > 1:
            raise ValueError(
                "Multiple active semesters found for the current date. "
                "Please ensure semester dates do not overlap."
            )

        return current_semesters.first()  # type: ignore[return-value]

    class Meta:
        ordering = ("-start_date",)


class CourseQuerySet(models.QuerySet["Course"]):
    def for_user(self, user: User) -> CourseQuerySet:
        """Courses the user is enrolled in as a student or leads."""
        return self.filter(Q(students__user=user) | Q(leaders=user)).distinct()

    def active(self) -> CourseQuerySet:
        """Courses belonging to a semester that today falls inside of."""
        today = timezone.now().date()
        return self.filter(
            semester__start_date__lte=today, semester__end_date__gte=today
        )

    def not_ended(self) -> CourseQuerySet:
        """Courses in a semester that has not finished, the ones yet to start
        included.

        A class is worth showing as soon as it exists: instructors fill theirs
        in before the semester opens, and students are enrolled ahead of it
        too, so waiting for the start date hides a class from the very people
        getting ready for it.
        """
        return self.filter(semester__end_date__gte=timezone.now().date())


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

    objects: ClassVar[CourseQuerySet] = CourseQuerySet.as_manager()  # type: ignore[assignment]

    def __str__(self) -> str:
        return f"{self.name} ({self.semester.name})"

    def get_absolute_url(self) -> str:
        return reverse("courses:course_detail", kwargs={"pk": self.pk})

    def is_managed_by(self, user: AbstractBaseUser | AnonymousUser) -> bool:
        """Whether the user may edit this course and manage its meetings."""
        if not user.is_authenticated:
            return False
        return bool(
            getattr(user, "is_staff", False) or self.leaders.filter(pk=user.pk).exists()
        )

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
    #: Length of airtable_name; named so forms can check it without _meta.
    NAME_MAX_LENGTH = 80

    class House(models.TextChoices):
        BLOB = "blob", "Blobs"
        BUNNY = "bunny", "Bunnies"
        CAT = "cat", "Cats"
        OWL = "owl", "Owls"
        RED_PANDA = "red_panda", "Red Panda"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="students",
    )
    airtable_name = models.CharField(
        max_length=NAME_MAX_LENGTH,
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


class GlobalEventQuerySet(models.QuerySet["GlobalEvent"]):
    def visible_to(self, user: User) -> GlobalEventQuerySet:
        """Events in visible semesters; non-staff only see semesters they are in."""
        qs = self.filter(semester__visible=True).select_related("semester")
        if user.is_staff:
            return qs
        return qs.filter(semester__students__user=user).distinct()

    def current_for(self, user: User) -> GlobalEventQuerySet:
        """The events of this semester, chronologically: what "this semester"
        means to a student is the semester they are enrolled in right now, and
        to staff every semester running right now."""
        return (
            self.visible_to(user)
            .filter(semester__in=Semester.objects.active())
            .order_by("start_time")
        )


class GlobalEvent(models.Model):
    """All-student events not attached to any particular club/course."""

    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="global_events"
    )
    title = models.CharField(max_length=200, help_text="Title of the event.")
    start_time = models.DateTimeField(help_text="When this event starts.")
    description = models.TextField(
        blank=True, help_text="Optional description of the event."
    )
    link = models.URLField(
        blank=True, help_text="Optional link (e.g. Zoom meeting link)."
    )

    objects: ClassVar[GlobalEventQuerySet] = GlobalEventQuerySet.as_manager()  # type: ignore[assignment]

    def __str__(self) -> str:
        return f"{self.title} ({self.start_time})"

    def get_absolute_url(self) -> str:
        return reverse("courses:global_event_detail", kwargs={"pk": self.pk})

    class Meta:
        ordering = ("start_time",)


def _default_token() -> str:
    return secrets.token_hex(32)


class CalendarToken(models.Model):
    """Per-user secret token for the iCalendar feed URL."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="calendar_token",
    )
    token = models.CharField(max_length=64, unique=True, default=_default_token)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"CalendarToken for {self.user}"
