from datetime import date

from atheweb.validators import VALIDATOR_WITH_FIGURES
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
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


class BlogPost(models.Model):
    """A blog post written by students, subject to staff review before publication."""

    title = models.CharField(max_length=200, help_text="Title of the blog post")
    subtitle = models.CharField(
        max_length=300, blank=True, help_text="Optional subtitle for the blog post"
    )
    slug = models.SlugField(
        unique=True, max_length=200, help_text="URL-friendly slug for the post"
    )
    display_author = models.CharField(
        max_length=100, help_text="Author name as displayed on the post"
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="blog_posts",
        help_text="User who created this post",
    )
    content = MarkdownField(
        rendered_field="content_rendered",
        validator=VALIDATOR_WITH_FIGURES,
        help_text="Blog post content in Markdown format",
    )
    content_rendered = RenderedMarkdownField()
    display_date = models.DateField(
        default=date.today,
        help_text="Date to display on the post (defaults to creation date)",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Date and time when the post was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Date and time when the post was last updated"
    )
    published = models.BooleanField(
        default=False,
        help_text="Whether the post is published. Unpublished posts are pending review.",
    )

    class Meta:
        ordering = ["-display_date", "-created_at"]
        verbose_name = "Blog Post"
        verbose_name_plural = "Blog Posts"

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("weblog:blog_detail", kwargs={"slug": self.slug})
