from django.contrib.auth.models import User
from django.db import models
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD


class StaffPhotoListing(models.Model):
    """Staff member photo listing with biography."""

    CATEGORY_CHOICES = [
        ("board", "Board"),
        ("teachers", "Teachers"),
        ("tas", "TAs"),
        ("past", "Past Staff"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        help_text="Django user account for this staff member",
    )
    display_name = models.CharField(
        max_length=100, help_text="Name to display on the staff page"
    )
    role = models.CharField(max_length=100, help_text="Role/title (e.g., President)")
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
        help_text="Ordering priority (0 for alphabetical, higher numbers come first)",
    )

    class Meta:
        ordering = ["-ordering", "display_name"]
        verbose_name = "Staff Photo Listing"
        verbose_name_plural = "Staff Photo Listings"

    def __str__(self) -> str:
        return f"{self.display_name} ({self.get_category_display()})"
