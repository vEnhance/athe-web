from django.db import models
from home.models import StaffPhotoListing


class Semester(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    start_date = models.DateField(help_text="When this semester starts")
    end_date = models.DateField(help_text="When this semester ends")

    def __str__(self) -> str:
        return self.name

    class Meta:
        ordering = ("-start_date",)


class Course(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="courses"
    )
    instructor = models.ForeignKey(
        StaffPhotoListing,
        null=True,
        on_delete=models.SET_NULL,
        related_name="courses",
        help_text="Link to the instructor for this course.",
    )
    difficulty = models.CharField(
        blank=True,
        max_length=80,
        help_text="Estimate of the difficulty of this course.",
    )
    lesson_plan = models.TextField(
        blank=True, help_text="List of lessons planned for this course. One per line."
    )

    def __str__(self) -> str:
        return self.name
