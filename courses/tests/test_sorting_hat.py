from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student


@pytest.mark.django_db
def test_sorting_hat_requires_superuser():
    """Test that only superusers can access the Sorting Hat view."""
    client = Client()

    # Test with non-authenticated user
    url = reverse("courses:sorting_hat")
    response = client.get(url)
    assert response.status_code == 302
    assert "/login/" in response.url

    # Test with regular user
    User.objects.create_user(username="regular", password="password")
    client.login(username="regular", password="password")
    response = client.get(url)
    assert response.status_code == 403

    # Test with staff (but not superuser)
    User.objects.create_user(username="staff", password="password", is_staff=True)
    client.login(username="staff", password="password")
    response = client.get(url)
    assert response.status_code == 403

    # Test with superuser
    User.objects.create_user(username="super", password="password", is_superuser=True)
    client.login(username="super", password="password")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_sorting_hat_get_displays_form():
    """Test that GET request displays the Sorting Hat form."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create a semester
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")
    response = client.get(url)

    assert response.status_code == 200
    assert "form" in response.context
    # Check that all house fields are present
    content = response.content.decode()
    assert "Blob" in content
    assert "Cat" in content
    assert "Owl" in content
    assert "Red Panda" in content
    assert "Bunny" in content


@pytest.mark.django_db
def test_sorting_hat_assigns_students_to_houses():
    """Test that Sorting Hat correctly assigns students to houses."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students
    student1 = Student.objects.create(airtable_name="Alice", semester=semester)
    student2 = Student.objects.create(airtable_name="Bob", semester=semester)
    student3 = Student.objects.create(airtable_name="Charlie", semester=semester)

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Post sorting hat assignments
    response = client.post(
        url,
        {
            "semester": semester.id,
            "blob": "Alice\nBob",
            "cat": "Charlie",
            "owl": "",
            "red_panda": "",
            "bunny": "",
        },
    )

    assert response.status_code == 200
    assert "results" in response.context

    # Verify students were assigned correctly
    student1.refresh_from_db()
    student2.refresh_from_db()
    student3.refresh_from_db()

    assert student1.house == Student.House.BLOB
    assert student2.house == Student.House.BLOB
    assert student3.house == Student.House.CAT

    # Check results
    results = response.context["results"]
    assert len(results["assigned"]) == 3
    assert len(results["not_found"]) == 0


@pytest.mark.django_db
def test_sorting_hat_handles_not_found_students():
    """Test that Sorting Hat reports students that don't exist."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create one student
    student1 = Student.objects.create(airtable_name="Alice", semester=semester)

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Post sorting hat assignments with some non-existent students
    response = client.post(
        url,
        {
            "semester": semester.id,
            "blob": "Alice\nNonExistent1",
            "cat": "NonExistent2",
            "owl": "",
            "red_panda": "",
            "bunny": "",
        },
    )

    assert response.status_code == 200

    # Verify Alice was assigned
    student1.refresh_from_db()
    assert student1.house == Student.House.BLOB

    # Check results
    results = response.context["results"]
    assert len(results["assigned"]) == 1
    assert len(results["not_found"]) == 2
    assert "NonExistent1" in results["not_found"][0]
    assert "NonExistent2" in results["not_found"][1]


@pytest.mark.django_db
def test_sorting_hat_handles_whitespace():
    """Test that Sorting Hat handles whitespace and empty lines correctly."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students
    student1 = Student.objects.create(airtable_name="Alice", semester=semester)
    student2 = Student.objects.create(airtable_name="Bob", semester=semester)

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Post with whitespace and empty lines
    response = client.post(
        url,
        {
            "semester": semester.id,
            "blob": "  Alice  \n\n  Bob  \n\n",
            "cat": "",
            "owl": "",
            "red_panda": "",
            "bunny": "",
        },
    )

    assert response.status_code == 200

    # Verify both students were assigned
    student1.refresh_from_db()
    student2.refresh_from_db()

    assert student1.house == Student.House.BLOB
    assert student2.house == Student.House.BLOB

    results = response.context["results"]
    assert len(results["assigned"]) == 2
    assert len(results["not_found"]) == 0


@pytest.mark.django_db
def test_sorting_hat_query_optimization():
    """Test that Sorting Hat uses O(1) queries, not O(n)."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create many students
    num_students = 50
    student_names = [f"Student{i}" for i in range(num_students)]
    students = [
        Student(airtable_name=name, semester=semester) for name in student_names
    ]
    Student.objects.bulk_create(students)

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Assign all students to various houses
    blob_students = "\n".join(student_names[:10])
    cat_students = "\n".join(student_names[10:20])
    owl_students = "\n".join(student_names[20:30])
    red_panda_students = "\n".join(student_names[30:40])
    bunny_students = "\n".join(student_names[40:50])

    # Count queries
    with CaptureQueriesContext(connection) as context:
        response = client.post(
            url,
            {
                "semester": semester.id,
                "blob": blob_students,
                "cat": cat_students,
                "owl": owl_students,
                "red_panda": red_panda_students,
                "bunny": bunny_students,
            },
        )

    assert response.status_code == 200

    # Should use a constant number of queries regardless of student count:
    # 1. Session/auth queries (2-3)
    # 2. Fetch all students (1 SELECT)
    # 3. Bulk update students (1 UPDATE)
    # Total should be around 5-6 queries maximum
    assert len(context.captured_queries) <= 6, (
        f"Expected ≤6 queries, got {len(context.captured_queries)}. "
        f"Should be O(1), not O(n) with n={num_students}"
    )

    # Verify all students were assigned correctly
    results = response.context["results"]
    assert len(results["assigned"]) == num_students
    assert len(results["not_found"]) == 0


@pytest.mark.django_db
def test_sorting_hat_same_semester_constraint():
    """Test that Sorting Hat only assigns students from the selected semester."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    # Create two semesters
    fall_semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    spring_semester = Semester.objects.create(
        name="Spring 2026",
        slug="sp26",
        start_date=(timezone.now() + timedelta(days=120)).date(),
        end_date=(timezone.now() + timedelta(days=210)).date(),
    )

    # Create students with same name in different semesters
    fall_alice = Student.objects.create(airtable_name="Alice", semester=fall_semester)
    spring_alice = Student.objects.create(
        airtable_name="Alice", semester=spring_semester
    )

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Assign Alice in fall semester
    response = client.post(
        url,
        {
            "semester": fall_semester.id,
            "blob": "Alice",
            "cat": "",
            "owl": "",
            "red_panda": "",
            "bunny": "",
        },
    )

    assert response.status_code == 200

    # Only fall Alice should be assigned
    fall_alice.refresh_from_db()
    spring_alice.refresh_from_db()

    assert fall_alice.house == Student.House.BLOB
    assert spring_alice.house == ""  # Should not be assigned


@pytest.mark.django_db
def test_sorting_hat_invalid_form():
    """Test that Sorting Hat handles invalid form submissions."""
    client = Client()
    User.objects.create_user(username="super", password="password", is_superuser=True)

    client.login(username="super", password="password")
    url = reverse("courses:sorting_hat")

    # Post without semester
    response = client.post(
        url,
        {
            "blob": "Alice",
            "cat": "",
            "owl": "",
            "red_panda": "",
            "bunny": "",
        },
    )

    # Should re-render form with errors
    assert response.status_code == 200
    assert "form" in response.context
    assert not response.context["form"].is_valid()
