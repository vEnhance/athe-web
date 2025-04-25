import pytest
from courses.models import Semester, Course


@pytest.mark.django_db
def test_course_creation():
    fall = Semester.objects.create(name="Fall 2025", slug="fall-2025")
    course = Course.objects.create(
        name="Intro to Django",
        description="Learn the basics of Django web development.",
        semester=fall,
    )

    assert course.name == "Intro to Django"
    assert course.semester.slug == "fa25"
    assert fall.courses.count() == 1
    assert fall.courses.first().name == "Intro to Django"
