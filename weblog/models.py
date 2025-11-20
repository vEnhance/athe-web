from django.db import models
from markdownfield.models import MarkdownField, RenderedMarkdownField
from markdownfield.validators import VALIDATOR_STANDARD


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
        validator=VALIDATOR_STANDARD,
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
