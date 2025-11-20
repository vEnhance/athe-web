from atheweb.validators import VALIDATOR_WITH_FIGURES
from django.db import models
from markdownfield.models import MarkdownField, RenderedMarkdownField


class Photo(models.Model):
    """Photo model for uploading images to reference in markdown."""

    name = models.CharField(
        max_length=200, help_text="Name or caption for the photo (for identification)"
    )
    image = models.ImageField(upload_to="photos/", help_text="Photo file to upload")
    uploaded_at = models.DateTimeField(
        auto_now_add=True, help_text="Date and time when the photo was uploaded"
    )

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Photo"
        verbose_name_plural = "Photos"

    def __str__(self) -> str:
        return self.name

    @property
    def markdown_url(self) -> str:
        """Return the URL path for use in markdown."""
        return f"/media/{self.image.name}"


class HistoryEntry(models.Model):
    """A history entry for the athemath program."""

    title = models.CharField(max_length=200, help_text="Title of the history entry")
    slug = models.SlugField(
        unique=True, max_length=200, help_text="URL-friendly slug for anchor links"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Date and time when the entry was created"
    )
    content = MarkdownField(
        rendered_field="content_rendered",
        validator=VALIDATOR_WITH_FIGURES,
        help_text="History entry content in Markdown format",
    )
    content_rendered = RenderedMarkdownField()
    visible = models.BooleanField(
        default=True, help_text="Whether the entry is visible to the public"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "History Entry"
        verbose_name_plural = "History Entries"

    def __str__(self) -> str:
        return self.title
