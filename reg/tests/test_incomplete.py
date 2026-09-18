"""The nag list of students who have not finished the questionnaire."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Semester, Student
from reg.models import StudentRegistration

URL = reverse("reg:incomplete-registrations")
ALL_STEPS = ("you", "classes", "availability", "sorting")


def register(student: Student, *steps: str, **kwargs: Any) -> StudentRegistration:
    first_name = student.airtable_name.split()[0].lower()
    defaults = {
        "email": f"{first_name}@example.com",
        "parent_email": "parent@example.com",
        "discord_username": first_name,
    }
    return StudentRegistration.objects.create(
        student=student, completed_steps=list(steps), **(defaults | kwargs)
    )


@pytest.fixture
def greta(athe: AtheClient, make_user: Callable[..., User]) -> User:
    return athe.login(make_user("greta", is_superuser=True, is_staff=True))


@pytest.mark.django_db
def test_requires_superuser(athe: AtheClient, make_user: Callable[..., User]) -> None:
    athe.get_redirects(reverse("login"), URL)

    athe.login(make_user("ta", is_staff=True))
    athe.get_redirects(reverse("index"), URL)


@pytest.mark.django_db
def test_lists_only_the_unfinished(
    athe: AtheClient,
    greta: User,
    semester: Semester,
    make_student: Callable[..., Student],
) -> None:
    finished = make_student(semester, airtable_name="Alice Anderson")
    register(finished, *ALL_STEPS)
    partway = make_student(semester, airtable_name="Bob Brown")
    register(partway, "you", "classes")
    unstarted = make_student(semester, airtable_name="Carol Clark")

    response = athe.get_ok(URL)
    assert response.context["semester"] == semester
    assert response.context["roster_size"] == 3
    assert [row["student"] for row in response.context["rows"]] == [partway, unstarted]
    assert [row["pages_done"] for row in response.context["rows"]] == [2, 0]

    assert athe.texts_of(response, "incomplete-name") == ["Bob Brown", "Carol Clark"]
    assert athe.texts_of(response, "incomplete-pages") == ["2/4", "0/4"]
    assert athe.texts_of(response, "incomplete-email") == ["bob@example.com"]
    assert athe.texts_of(response, "incomplete-discord") == ["bob"]
    athe.assert_testid_count(response, "incomplete-unstarted", 1)


@pytest.mark.django_db
def test_an_unstarted_student_leaks_nothing_but_their_roster_name(
    athe: AtheClient,
    greta: User,
    semester: Semester,
    make_student: Callable[..., Student],
    make_user: Callable[..., User],
) -> None:
    """A claimed name with no answers still only has the Airtable name to show."""
    user = make_user("carol", email="carol@example.com")
    make_student(semester, user=user, airtable_name="Carol Clark")

    response = athe.get_ok(URL)
    assert response.context["rows"][0]["registration"] is None
    assert b"carol@example.com" not in response.content


@pytest.mark.django_db
def test_everyone_finished(
    athe: AtheClient,
    greta: User,
    semester: Semester,
    make_student: Callable[..., Student],
) -> None:
    register(make_student(semester, airtable_name="Alice Anderson"), *ALL_STEPS)

    response = athe.get_ok(URL)
    assert response.context["rows"] == []
    athe.assert_testid(response, "incomplete-nobody")


@pytest.mark.django_db
def test_without_a_semester(athe: AtheClient, greta: User) -> None:
    response = athe.get_ok(URL)
    assert response.context["semester"] is None
    assert response.context["rows"] == []
    athe.assert_testid(response, "incomplete-no-semester")


@pytest.mark.django_db
def test_a_named_semester_overrides_the_current_one(
    athe: AtheClient,
    greta: User,
    semester: Semester,
    make_semester: Callable[..., Semester],
    make_student: Callable[..., Student],
) -> None:
    today = timezone.localdate()
    old = make_semester(
        "Spring 2025",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=100),
    )
    make_student(semester, airtable_name="Alice Anderson")
    make_student(old, airtable_name="Zach Zhang")

    response = athe.get_ok(
        reverse("reg:incomplete-registrations", kwargs={"slug": old.slug})
    )
    assert response.context["semester"] == old
    assert athe.texts_of(response, "incomplete-name") == ["Zach Zhang"]

    assert athe.get("/reg/incomplete/no-such-semester/").status_code == 404


@pytest.mark.django_db
def test_other_semesters_are_linked_but_not_the_one_shown(
    athe: AtheClient,
    greta: User,
    semester: Semester,
    make_semester: Callable[..., Semester],
) -> None:
    today = timezone.localdate()
    old = make_semester(
        "Spring 2025",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=100),
    )

    response = athe.get_ok(URL)
    assert list(response.context["semesters"]) == [old]
    assert athe.texts_of(response, "incomplete-semester-link") == ["Spring 2025"]
