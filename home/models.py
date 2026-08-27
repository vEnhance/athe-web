from typing import ClassVar

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import AnonymousUser, User
from django.db import models
from django.urls import reverse
from markdownfield.models import MarkdownField, RenderedMarkdownField

from atheweb.validators import VALIDATOR_WITH_FIGURES


class ApplyPSet(models.Model):
    """Application Problem Set model."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"

    name = models.CharField(
        max_length=200,
        help_text="Name of the problem set (e.g., 'Fall 2025')",
    )
    deadline = models.DateField(
        help_text="Application deadline",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        help_text="Status of the problem set",
    )
    file = models.FileField(
        null=True,
        blank=True,
        upload_to="apply_psets/",
        help_text="PDF file for the problem set",
    )
    instructions = MarkdownField(
        blank=True,
        rendered_field="instructions_rendered",
        validator=VALIDATOR_WITH_FIGURES,
        help_text="Instructions displayed when status is active (Markdown format)",
    )
    instructions_rendered = RenderedMarkdownField()
    closed_message = MarkdownField(
        blank=True,
        rendered_field="closed_message_rendered",
        validator=VALIDATOR_WITH_FIGURES,
        help_text="Message displayed when applications are closed (Markdown format)",
    )
    closed_message_rendered = RenderedMarkdownField()

    class Meta:
        ordering = ["-deadline"]
        verbose_name = "Application Problem Set"
        verbose_name_plural = "Application Problem Sets"

    def __str__(self) -> str:
        return self.name


class StaffPhotoListingQuerySet(models.QuerySet["StaffPhotoListing"]):
    def active(self) -> StaffPhotoListingQuerySet:
        """Listings for staff who are still on the team.

        Past staff keep their listing so their name survives on the site, but
        they are no longer staff for any purpose that grants them something.
        """
        return self.exclude(category=StaffPhotoListing.Category.XSTAFF)


class StaffPhotoListing(models.Model):
    """Staff member photo listing with biography."""

    class Category(models.TextChoices):
        BOARD = "board", "Board"
        INSTRUCTOR = "instructor", "Current Instructors"
        TA = "ta", "TAs"
        XSTAFF = "xstaff", "Past Staff"

    user = models.OneToOneField(
        User,
        null=True,
        blank=True,
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
        choices=Category.choices,
        help_text="Staff category",
    )
    biography = MarkdownField(
        rendered_field="biography_rendered",
        validator=VALIDATOR_WITH_FIGURES,
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
    website = models.URLField(
        blank=True,
        help_text="Personal website URL",
    )
    email = models.EmailField(
        blank=True,
        help_text="Contact email address",
    )
    instagram_username = models.CharField(
        max_length=30,
        blank=True,
        help_text="Instagram username (without @)",
    )
    discord_username = models.CharField(
        max_length=32,
        blank=True,
        help_text="Discord username",
    )
    github_username = models.CharField(
        max_length=39,
        blank=True,
        help_text="GitHub username",
    )

    objects: ClassVar[StaffPhotoListingQuerySet] = (
        StaffPhotoListingQuerySet.as_manager()
    )  # type: ignore[assignment]

    class Meta:
        ordering = ["category", "-ordering", "display_name"]
        verbose_name = "Staff Photo Listing"
        verbose_name_plural = "Staff Photo Listings"

    def __str__(self) -> str:
        return self.display_name

    @classmethod
    def is_current_staff(cls, user: AbstractBaseUser | AnonymousUser) -> bool:
        """Whether this user has a listing that says they are staff right now."""
        if not user.is_authenticated:
            return False
        return cls.objects.active().filter(user=user).exists()

    def get_absolute_url(self) -> str:
        """Return the absolute URL for this staff member."""
        return reverse("home:staff_detail", kwargs={"slug": self.slug})
