import uuid

from django.db import models
from django.urls import reverse
from django.utils import timezone


class InviteLink(models.Model):
    """A shareable, expiring link that lets someone claim an existing record."""

    #: URL name this kind of invite is served at.
    url_name: str

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=100,
        help_text="A descriptive name for this invite link, e.g. 'Spring 2025'",
    )
    expiration_date = models.DateTimeField(
        help_text="Date and time when this invite link expires"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]

    def is_expired(self) -> bool:
        """Check if this invite link has expired."""
        return timezone.now() > self.expiration_date

    def get_absolute_url(self) -> str:
        """Get the URL for this invite link."""
        return reverse(self.url_name, kwargs={"invite_id": self.id})


class StaffInviteLink(InviteLink):
    """
    An invite link for staff members to register and connect to their StaffPhotoListing.
    """

    url_name = "reg:add-staff"

    class Meta(InviteLink.Meta):
        verbose_name = "Staff Invite Link"
        verbose_name_plural = "Staff Invite Links"

    def __str__(self) -> str:
        return (
            f"{self.name} (expires {self.expiration_date.strftime('%Y-%m-%d %H:%M')})"
        )


class StudentInviteLink(InviteLink):
    """
    An invite link for students to register and connect to their Student record.
    """

    url_name = "reg:add-student"

    semester = models.ForeignKey(
        "courses.Semester",
        on_delete=models.CASCADE,
        related_name="invite_links",
        help_text="The semester this invite link is for",
    )

    class Meta(InviteLink.Meta):
        verbose_name = "Student Invite Link"
        verbose_name_plural = "Student Invite Links"

    def __str__(self) -> str:
        return (
            f"{self.name} - {self.semester} "
            f"(expires {self.expiration_date.strftime('%Y-%m-%d %H:%M')})"
        )

    def is_semester_ended(self) -> bool:
        """Check if the semester has ended."""
        return timezone.localdate() > self.semester.end_date
