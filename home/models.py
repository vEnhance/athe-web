from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD


class ApplyPSet(models.Model):
    """Application Problem Set model."""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("completed", "Completed"),
    ]

    name = models.CharField(
        max_length=200,
        help_text="Name of the problem set (e.g., 'Fall 2025 PSet')",
    )
    deadline = models.DateTimeField(
        help_text="Application deadline",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Status of the problem set",
    )
    file = models.FileField(
        null=True,
        blank=True,
        upload_to="apply_psets/",
        help_text="PDF file for the problem set",
    )
    instructions = MarkdownField(
        rendered_field="instructions_rendered",
        validator=VALIDATOR_STANDARD,
        help_text="Instructions displayed when status is active (Markdown format)",
    )
    instructions_rendered = RenderedMarkdownField()
    closed_message = MarkdownField(
        rendered_field="closed_message_rendered",
        validator=VALIDATOR_STANDARD,
        help_text="Message displayed when applications are closed (Markdown format)",
    )
    closed_message_rendered = RenderedMarkdownField()

    class Meta:
        ordering = ["-deadline"]
        verbose_name = "Application Problem Set"
        verbose_name_plural = "Application Problem Sets"

    def __str__(self) -> str:
        return self.name


class StaffPhotoListing(models.Model):
    """Staff member photo listing with biography."""

    CATEGORY_CHOICES = [
        ("board", "Board"),
        ("instructor", "Current Instructors"),
        ("ta", "TAs"),
        ("xstaff", "Past Staff"),
    ]

    user = models.OneToOneField(
        User,
        null=True,
        on_delete=models.CASCADE,
        help_text="Django user account for this staff member",
    )
    display_name = models.CharField(
        max_length=100, help_text="Name to display on the staff page"
    )
    slug = models.SlugField(
        unique=True, max_length=100, help_text="URL-friendly slug for staff member"
    )
    role = models.CharField(max_length=100, help_text="Role or title")
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        help_text="Staff category",
    )
    biography = MarkdownField(
        rendered_field="biography_rendered",
        validator=VALIDATOR_STANDARD,
        help_text="Biography in Markdown format",
    )
    biography_rendered = RenderedMarkdownField()
    photo = models.ImageField(
        upload_to="staff_photos/",
        help_text="Staff member photo",
    )
    ordering = models.IntegerField(
        default=0,
        help_text="Ordering priority (higher numbers come first)",
    )

    class Meta:
        ordering = ["category", "-ordering", "display_name"]
        verbose_name = "Staff Photo Listing"
        verbose_name_plural = "Staff Photo Listings"

    def __str__(self) -> str:
        return self.display_name

    def get_absolute_url(self) -> str:
        """Return the absolute URL for this staff member."""
        return reverse("home:staff_detail", kwargs={"slug": self.slug})
