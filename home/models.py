from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD


class StaffPhotoListing(models.Model):
    """Staff member photo listing with biography."""

    CATEGORY_CHOICES = [
        ("board", "Board"),
        ("teachers", "Current Instructors"),
        ("tas", "TAs"),
        ("past", "Past Staff"),
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
