from django.core.validators import MaxLengthValidator
from django.db import models


class YearbookEntry(models.Model):
    """A student's yearbook entry for a semester."""

    student = models.OneToOneField(
        "courses.Student",
        on_delete=models.CASCADE,
        related_name="yearbook_entry",
    )
    display_name = models.CharField(
        max_length=100,
        help_text="How you want your name displayed to other students.",
    )
    bio = models.TextField(
        validators=[MaxLengthValidator(1000)],
        help_text="Tell us about yourself! (Max 1000 characters)",
    )

    # Optional social media / website fields
    discord_username = models.CharField(
        max_length=100,
        blank=True,
        help_text="Your Discord username (e.g., username#1234 or just username).",
    )
    instagram_username = models.CharField(
        max_length=100,
        blank=True,
        help_text="Your Instagram username (without the @).",
    )
    github_username = models.CharField(
        max_length=100,
        blank=True,
        help_text="Your GitHub username.",
    )
    website_url = models.URLField(
        blank=True,
        help_text="Your personal website URL.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.display_name} ({self.student.semester})"

    class Meta:
        verbose_name = "Yearbook Entry"
        verbose_name_plural = "Yearbook Entries"
        ordering = ("student__house", "display_name")
