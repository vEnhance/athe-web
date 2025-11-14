import pytest
from django.utils import timezone

from courses.models import Course, Semester


@pytest.mark.django_db
def test_course_creation():
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now(),
        end_date=timezone.now(),
    )
    course = Course.objects.create(
        name="Intro to Django",
        description="Learn the basics of Django web development.",
        semester=fall,
    )

    assert course.name == "Intro to Django"
    assert course.semester.slug == "fa25"
