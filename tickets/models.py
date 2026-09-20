from typing import ClassVar

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseMeeting, Student

#: How far ahead of now a student may pick an office hours sitting.
MEETING_HORIZON_DAYS = 15


class TicketQuerySet(models.QuerySet["Ticket"]):
    def open(self) -> TicketQuerySet:
        return self.filter(resolved_at__isnull=True)

    def resolved(self) -> TicketQuerySet:
        return self.filter(resolved_at__isnull=False)

    def for_review(self) -> TicketQuerySet:
        """Every ticket on the staff list, oldest first so the queue is a queue."""
        return self.select_related(
            "student", "student__user", "meeting", "meeting__course"
        ).order_by("created_at")

    def followed_by(self, user: AbstractBaseUser | AnonymousUser) -> TicketQuerySet:
        """Tickets aimed at an office hours session this staff member follows."""
        return self.filter(meeting__course__in=Course.objects.followed_by(user))


class Ticket(models.Model):
    """A question a student wants answered, at office hours or over Discord."""

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="tickets"
    )
    title = models.CharField(
        max_length=80,
        help_text="Where is your problem from? If it's a general question, "
        "describe what it's about.",
    )
    question = models.TextField(
        help_text="Write out your question. LaTeX between dollar signs, like "
        "$x^2+1$, will be typeset.",
    )
    meeting = models.ForeignKey(
        CourseMeeting,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tickets",
        help_text="The office hours sitting to answer this at. Left empty, the "
        "question is answered over Discord DM instead.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="resolved_tickets",
    )
    staff_notes = models.TextField(
        blank=True, help_text="Notes for staff; students do not see these."
    )

    objects: ClassVar[TicketQuerySet] = TicketQuerySet.as_manager()  # type: ignore[assignment]

    def __str__(self) -> str:
        return f"{self.title} ({self.student})"

    def get_absolute_url(self) -> str:
        return reverse("tickets:review_detail", kwargs={"pk": self.pk})

    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None

    @property
    def destination(self) -> str:
        """Where the student asked for an answer, for one column of a table."""
        if self.meeting is None:
            return "Discord DM"
        return self.meeting.course.name

    def resolve(self, user: AbstractBaseUser) -> None:
        self.resolved_at = timezone.now()
        self.resolved_by = user  # type: ignore[assignment]

    def unresolve(self) -> None:
        self.resolved_at = None
        self.resolved_by = None

    def clean(self) -> None:
        super().clean()
        if self.meeting is not None and not self.meeting.course.is_office_hours:
            raise ValidationError(
                {"meeting": "Questions can only be sent to an office hours session."}
            )

    class Meta:
        ordering = ("-created_at",)
