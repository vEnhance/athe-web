from collections.abc import Callable
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Course, Semester

SEMESTER_LIST = reverse("courses:semester_list")


@pytest.mark.django_db
def test_semester_list_counts_classes_only(
    athe: AtheClient, semester: Semester, make_course: Callable[..., Course]
):
    """The count beside a semester matches its catalog, which excludes clubs."""
    for name in ("Algebra", "Geometry"):
        make_course(semester, name=name)
    for name in ("Chess Club", "Japanese Club", "Art Club"):
        make_course(semester, name=name, is_club=True)

    response = athe.get_ok(SEMESTER_LIST)

    assert response.context["semesters"].get().class_count == 2
    assert athe.text_of(response, "semester-class-count") == "2 classes"


@pytest.mark.django_db
def test_semester_list_counts_are_per_semester_and_pluralized(
    athe: AtheClient,
    semester: Semester,
    make_semester: Callable[..., Semester],
    make_course: Callable[..., Course],
):
    """A semester with one class says so, and does not borrow another's count."""
    today = timezone.localdate()
    spring = make_semester(
        name="Spring Semester",
        start_date=today + timedelta(days=120),
        end_date=today + timedelta(days=210),
    )
    make_course(semester, name="Algebra")
    make_course(spring, name="Chess Club", is_club=True)

    response = athe.get_ok(SEMESTER_LIST)

    counts = {s.name: s.class_count for s in response.context["semesters"]}
    assert counts == {"Fall 2025": 1, "Spring Semester": 0}
    assert sorted(athe.texts_of(response, "semester-class-count")) == [
        "0 classes",
        "1 class",
    ]


@pytest.mark.django_db
def test_semester_list_is_empty_before_there_are_any(athe: AtheClient):
    response = athe.get_ok(SEMESTER_LIST)

    assert list(response.context["semesters"]) == []
    athe.assert_testid(response, "semester-list-empty")
