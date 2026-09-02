from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester


@pytest.mark.django_db
def test_semester_list_counts_classes_only():
    """The count beside a semester matches its catalog, which excludes clubs."""
    semester = Semester.objects.create(
        name="Fall Semester",
        slug="fall",
        start_date=timezone.localdate(),
        end_date=timezone.localdate() + timedelta(days=90),
    )
    for name in ("Algebra", "Geometry"):
        Course.objects.create(
            name=name, description=name, semester=semester, is_club=False
        )
    for name in ("Chess Club", "Japanese Club", "Art Club"):
        Course.objects.create(
            name=name, description=name, semester=semester, is_club=True
        )

    response = Client().get(reverse("courses:semester_list"))

    assert response.context["semesters"].get().class_count == 2
    assert "2 classes" in response.content.decode()


@pytest.mark.django_db
def test_semester_list_counts_are_per_semester_and_pluralized():
    """A semester with one class says so, and does not borrow another's count."""
    fall = Semester.objects.create(
        name="Fall Semester",
        slug="fall",
        start_date=timezone.localdate(),
        end_date=timezone.localdate() + timedelta(days=90),
    )
    spring = Semester.objects.create(
        name="Spring Semester",
        slug="spring",
        start_date=timezone.localdate() + timedelta(days=120),
        end_date=timezone.localdate() + timedelta(days=210),
    )
    Course.objects.create(
        name="Algebra", description="Algebra", semester=fall, is_club=False
    )
    Course.objects.create(
        name="Chess Club", description="Chess", semester=spring, is_club=True
    )

    response = Client().get(reverse("courses:semester_list"))

    counts = {s.name: s.class_count for s in response.context["semesters"]}
    assert counts == {"Fall Semester": 1, "Spring Semester": 0}

    content = response.content.decode()
    assert "1 class" in content
    assert "1 classes" not in content
    assert "0 classes" in content
