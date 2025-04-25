from django.db import models


class Semester(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)

    def __str__(self):
        return self.name


class Course(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    semester = models.ForeignKey(
        Semester, on_delete=models.CASCADE, related_name="courses"
    )

    def __str__(self):
        return self.name
