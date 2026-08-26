"""The two endpoints Greta drives the class matching through."""

import json
from datetime import timedelta
from io import BytesIO

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student
from reg.models import CoursePreference, StudentRegistration


@pytest.fixture
def semester():
    today = timezone.now().date()
    return Semester.objects.create(
        name="Fall 2025",
        slug="fall-2025",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=90),
    )


@pytest.fixture
def courses(semester):
    return {
        name: Course.objects.create(
            name=name, description=name, semester=semester, is_club=is_club
        )
        for name, is_club in (("Algebra", False), ("Geometry", False), ("Chess", True))
    }


@pytest.fixture
def students(semester):
    return {
        name: Student.objects.create(airtable_name=name, semester=semester)
        for name in ("Alice Anderson", "Bob Brown")
    }


@pytest.fixture
def registration(students, courses):
    registration = StudentRegistration.objects.create(
        student=students["Alice Anderson"],
        email="alice@example.com",
        parent_email="parent@example.com",
        discord_username="alice",
        course_comments="No 8am please",
        availability=["sat-1000", "sun-1030"],
        availability_comments="Weekends only",
        subject_interest={
            "algebra": "very",
            "combinatorics": "somewhat",
            "geometry": "not",
            "number_theory": "very",
        },
        difficulty_levels=["aime", "olympiad"],
        completed_steps=["you", "classes", "availability", "sorting"],
        quiz_challenge="plan",
        quiz_values="clarity",
        quiz_compass="logic",
        quiz_day_off="productive",
        quiz_friend="trustworthy",
        house_request="Owls",
    )
    CoursePreference.objects.create(
        registration=registration, course=courses["Geometry"], rank=1
    )
    CoursePreference.objects.create(
        registration=registration, course=courses["Algebra"], already_taken=True
    )
    return registration


@pytest.fixture
def superuser_client():
    User.objects.create_user(username="greta", password="password", is_superuser=True)
    client = Client()
    client.login(username="greta", password="password")
    return client


@pytest.fixture
def responses_url(semester):
    return reverse("reg:responses", kwargs={"slug": semester.slug})


UPLOAD_URL = reverse("reg:upload-assignments")


def upload(client, semester, payload, **extra):
    return client.post(
        UPLOAD_URL,
        {"semester": semester.pk, "payload": json.dumps(payload), **extra},
    )


@pytest.mark.django_db
@pytest.mark.parametrize("url_name", ["responses", "upload"])
def test_endpoints_require_superuser(url_name, responses_url):
    url = responses_url if url_name == "responses" else UPLOAD_URL
    assert Client().get(url).status_code == 302

    User.objects.create_user(username="ta", password="password", is_staff=True)
    client = Client()
    client.login(username="ta", password="password")
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse("index")


@pytest.mark.django_db
def test_responses_download(
    superuser_client, responses_url, registration, students, courses
):
    response = superuser_client.get(responses_url)
    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    payload = json.loads(response.content)

    assert payload["semester"]["slug"] == "fall-2025"
    # Only classes are up for matching, so the club stays out of the download.
    assert [course["name"] for course in payload["courses"]] == ["Algebra", "Geometry"]
    assert len(payload["availability_slots"]) == 64
    assert payload["quiz_questions"]["quiz_challenge"]["choices"]["plan"]
    assert [subject["key"] for subject in payload["subjects"]] == [
        "algebra",
        "combinatorics",
        "geometry",
        "number_theory",
    ]
    assert {level["key"] for level in payload["difficulty_levels"]} >= {"amc", "aime"}

    by_name = {student["airtable_name"]: student for student in payload["students"]}
    alice = by_name["Alice Anderson"]["registration"]
    assert alice["email"] == "alice@example.com"
    assert alice["parent_email"] == "parent@example.com"
    assert alice["availability"] == ["sat-1000", "sun-1030"]
    assert alice["course_choices"] == [
        {"rank": 1, "course_id": courses["Geometry"].pk, "course": "Geometry"}
    ]
    assert alice["subject_interest"]["algebra"] == "very"
    assert alice["difficulty_levels"] == ["aime", "olympiad"]
    assert alice["complete"] is True
    assert [entry["course"] for entry in alice["courses_already_taken"]] == ["Algebra"]
    assert alice["quiz"]["quiz_challenge"] == "plan"
    assert alice["house_request"] == "Owls"

    # Students who have not answered are listed too, so gaps are obvious.
    assert by_name["Bob Brown"]["registration"] is None


@pytest.mark.django_db
def test_upload_assigns_courses_and_houses(
    superuser_client, semester, courses, students
):
    students["Alice Anderson"].enrolled_courses.add(courses["Chess"])

    response = upload(
        superuser_client,
        semester,
        {
            "semester": "fall-2025",
            "assignments": [
                {
                    "airtable_name": "Alice Anderson",
                    "courses": ["Algebra", "Geometry"],
                    "house": "owl",
                },
                {"id": students["Bob Brown"].pk, "courses": ["Algebra"]},
            ],
        },
    )
    assert response.status_code == 200
    assert not response.context["form"].errors

    alice = students["Alice Anderson"]
    alice.refresh_from_db()
    assert alice.house == Student.House.OWL
    assert set(alice.enrolled_courses.values_list("name", flat=True)) == {
        "Algebra",
        "Geometry",
        "Chess",  # a club they joined themselves survives the matching
    }

    bob = students["Bob Brown"]
    bob.refresh_from_db()
    assert list(bob.enrolled_courses.values_list("name", flat=True)) == ["Algebra"]
    assert bob.house == ""


@pytest.mark.django_db
def test_upload_replaces_previous_classes(
    superuser_client, semester, courses, students
):
    alice = students["Alice Anderson"]
    alice.enrolled_courses.add(courses["Algebra"])

    upload(
        superuser_client,
        semester,
        [{"airtable_name": "Alice Anderson", "courses": ["Geometry"]}],
    )
    assert list(alice.enrolled_courses.values_list("name", flat=True)) == ["Geometry"]


@pytest.mark.django_db
def test_upload_house_only_leaves_classes_alone(
    superuser_client, semester, courses, students
):
    alice = students["Alice Anderson"]
    alice.enrolled_courses.add(courses["Algebra"])

    upload(
        superuser_client,
        semester,
        [{"airtable_name": "Alice Anderson", "house": "cat"}],
    )
    alice.refresh_from_db()
    assert alice.house == Student.House.CAT
    assert list(alice.enrolled_courses.values_list("name", flat=True)) == ["Algebra"]


@pytest.mark.django_db
def test_upload_rejects_bad_data_without_applying_anything(
    superuser_client, semester, courses, students
):
    response = upload(
        superuser_client,
        semester,
        [
            {"airtable_name": "Nobody", "courses": ["Algebra"]},
            {"airtable_name": "Bob Brown", "courses": ["Astrology"]},
            {"airtable_name": "Alice Anderson", "house": "hufflepuff"},
        ],
    )
    assert response.status_code == 200
    errors = response.context["form"].errors["__all__"]
    assert any("no student 'Nobody'" in error for error in errors)
    assert any("Astrology" in error for error in errors)
    assert any("hufflepuff" in error for error in errors)
    assert not Student.objects.filter(enrolled_courses__isnull=False).exists()


@pytest.mark.django_db
def test_upload_rejects_duplicate_students(superuser_client, semester, students):
    response = upload(
        superuser_client,
        semester,
        [
            {"airtable_name": "Alice Anderson", "house": "cat"},
            {"airtable_name": "Alice Anderson", "house": "owl"},
        ],
    )
    assert any(
        "appears twice" in error for error in response.context["form"].errors["__all__"]
    )


@pytest.mark.django_db
def test_upload_rejects_wrong_semester(superuser_client, semester, students):
    response = upload(
        superuser_client,
        semester,
        {
            "semester": "spring-2024",
            "assignments": [{"airtable_name": "Alice Anderson", "house": "cat"}],
        },
    )
    assert any(
        "spring-2024" in error for error in response.context["form"].errors["__all__"]
    )


@pytest.mark.django_db
def test_upload_rejects_malformed_json(superuser_client, semester):
    response = superuser_client.post(
        UPLOAD_URL, {"semester": semester.pk, "payload": "{not json"}
    )
    assert any(
        "isn't valid JSON" in error
        for error in response.context["form"].errors["__all__"]
    )


@pytest.mark.django_db
def test_upload_accepts_a_file(superuser_client, semester, courses, students):
    payload = json.dumps(
        [{"airtable_name": "Bob Brown", "courses": ["Geometry"], "house": "blob"}]
    ).encode()
    upload_file = BytesIO(payload)
    upload_file.name = "assignments.json"

    response = superuser_client.post(
        UPLOAD_URL,
        {"semester": semester.pk, "payload": "", "payload_file": upload_file},
    )
    assert response.status_code == 200
    assert not response.context["form"].errors

    bob = students["Bob Brown"]
    bob.refresh_from_db()
    assert bob.house == Student.House.BLOB
    assert list(bob.enrolled_courses.values_list("name", flat=True)) == ["Geometry"]


@pytest.mark.django_db
def test_upload_requires_some_payload(superuser_client, semester):
    response = superuser_client.post(UPLOAD_URL, {"semester": semester.pk})
    assert any(
        "Paste some JSON" in error
        for error in response.context["form"].errors["__all__"]
    )
