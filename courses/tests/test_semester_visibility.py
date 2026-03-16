from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student


@pytest.mark.django_db
def test_semester_list_hides_invisible_from_non_staff():
    """Test that non-staff users cannot see invisible semesters in the semester list."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create visible and invisible semesters
    visible_semester = Semester.objects.create(
        name="Visible Semester",
        slug="visible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=True,
    )
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=(timezone.now() + timedelta(days=120)).date(),
        end_date=(timezone.now() + timedelta(days=210)).date(),
        visible=False,
    )

    client.login(username="student", password="password")
    url = reverse("courses:semester_list")
    response = client.get(url)

    content = response.content.decode()
    assert "Visible Semester" in content
    assert "Invisible Semester" not in content

    # Verify the context
    semesters = response.context["semesters"]
    semester_names = [s.name for s in semesters]
    assert visible_semester.name in semester_names
    assert invisible_semester.name not in semester_names


@pytest.mark.django_db
def test_semester_list_shows_all_to_staff():
    """Test that staff users can see all semesters including invisible ones."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create visible and invisible semesters
    visible_semester = Semester.objects.create(
        name="Visible Semester",
        slug="visible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=True,
    )
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=(timezone.now() + timedelta(days=120)).date(),
        end_date=(timezone.now() + timedelta(days=210)).date(),
        visible=False,
    )

    client.login(username="staff", password="password")
    url = reverse("courses:semester_list")
    response = client.get(url)

    content = response.content.decode()
    assert "Visible Semester" in content
    assert "Invisible Semester" in content

    # Verify the context
    semesters = response.context["semesters"]
    semester_names = [s.name for s in semesters]
    assert visible_semester.name in semester_names
    assert invisible_semester.name in semester_names


@pytest.mark.django_db
def test_course_list_invisible_semester_non_staff_404():
    """Test that non-staff users get 404 when accessing course list for invisible semester."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create an invisible semester
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )

    client.login(username="student", password="password")
    url = reverse("courses:course_list", kwargs={"slug": invisible_semester.slug})
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_course_list_invisible_semester_staff_access():
    """Test that staff users can access course list for invisible semesters."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create an invisible semester with a course
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )
    Course.objects.create(
        name="Test Course",
        description="Test",
        semester=invisible_semester,
        is_club=False,
    )

    client.login(username="staff", password="password")
    url = reverse("courses:course_list", kwargs={"slug": invisible_semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    assert "Test Course" in response.content.decode()


@pytest.mark.django_db
def test_course_detail_invisible_semester_non_staff_denied():
    """Test that non-staff users cannot access courses in invisible semesters."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")

    # Create an invisible semester
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )

    # Create a course and enroll the student
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=invisible_semester,
        is_club=False,
    )
    student = Student.objects.create(user=user, semester=invisible_semester)
    course.students.add(student)

    client.login(username="student", password="password")
    url = reverse("courses:course_detail", kwargs={"pk": course.pk})
    response = client.get(url)

    # Should get 403 even though student is enrolled
    assert response.status_code == 403


@pytest.mark.django_db
def test_course_detail_invisible_semester_staff_access():
    """Test that staff users can access courses in invisible semesters."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create an invisible semester
    invisible_semester = Semester.objects.create(
        name="Invisible Semester",
        slug="invisible",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )

    # Create a course
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=invisible_semester,
        is_club=False,
    )

    client.login(username="staff", password="password")
    url = reverse("courses:course_detail", kwargs={"pk": course.pk})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_catalog_root_skips_invisible_for_non_staff():
    """Test that catalog root redirects to the most recent visible semester for non-staff."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create semesters (most recent is invisible)
    older_visible = Semester.objects.create(
        name="Older Visible",
        slug="older",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )
    Semester.objects.create(
        name="Newer Invisible",
        slug="newer",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )

    client.login(username="student", password="password")
    url = reverse("courses:catalog_root")
    response = client.get(url)

    # Should redirect to the older visible semester
    assert response.status_code == 302
    assert response.url == reverse(
        "courses:course_list", kwargs={"slug": older_visible.slug}
    )


@pytest.mark.django_db
def test_catalog_root_includes_invisible_for_staff():
    """Test that catalog root redirects to the most recent semester (even if invisible) for staff."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create semesters (most recent is invisible)
    Semester.objects.create(
        name="Older Visible",
        slug="older",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
        visible=True,
    )
    newer_invisible = Semester.objects.create(
        name="Newer Invisible",
        slug="newer",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=False,
    )

    client.login(username="staff", password="password")
    url = reverse("courses:catalog_root")
    response = client.get(url)

    # Should redirect to the newer invisible semester
    assert response.status_code == 302
    assert response.url == reverse(
        "courses:course_list", kwargs={"slug": newer_invisible.slug}
    )


@pytest.mark.django_db
def test_course_list_navigation_skips_invisible_for_non_staff():
    """Test that previous/next semester navigation skips invisible semesters for non-staff."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    # Create three semesters: visible, invisible, visible
    older_visible = Semester.objects.create(
        name="Older Visible",
        slug="older",
        start_date=(timezone.now() - timedelta(days=200)).date(),
        end_date=(timezone.now() - timedelta(days=110)).date(),
        visible=True,
    )
    # Create middle invisible semester (not used directly, but necessary for test)
    Semester.objects.create(
        name="Middle Invisible",
        slug="middle",
        start_date=(timezone.now() - timedelta(days=100)).date(),
        end_date=(timezone.now() - timedelta(days=10)).date(),
        visible=False,
    )
    newer_visible = Semester.objects.create(
        name="Newer Visible",
        slug="newer",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=True,
    )

    client.login(username="student", password="password")

    # Access the newer visible semester
    url = reverse("courses:course_list", kwargs={"slug": newer_visible.slug})
    response = client.get(url)

    # Previous semester should skip the invisible one and go to older visible
    assert response.context["prev_semester"] == older_visible
    assert response.context["next_semester"] is None

    # Access the older visible semester
    url = reverse("courses:course_list", kwargs={"slug": older_visible.slug})
    response = client.get(url)

    # Next semester should skip the invisible one and go to newer visible
    assert response.context["prev_semester"] is None
    assert response.context["next_semester"] == newer_visible


@pytest.mark.django_db
def test_course_list_navigation_includes_invisible_for_staff():
    """Test that previous/next semester navigation includes invisible semesters for staff."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create three semesters: visible, invisible, visible
    older_visible = Semester.objects.create(
        name="Older Visible",
        slug="older",
        start_date=(timezone.now() - timedelta(days=200)).date(),
        end_date=(timezone.now() - timedelta(days=110)).date(),
        visible=True,
    )
    middle_invisible = Semester.objects.create(
        name="Middle Invisible",
        slug="middle",
        start_date=(timezone.now() - timedelta(days=100)).date(),
        end_date=(timezone.now() - timedelta(days=10)).date(),
        visible=False,
    )
    newer_visible = Semester.objects.create(
        name="Newer Visible",
        slug="newer",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        visible=True,
    )

    client.login(username="staff", password="password")

    # Access the newer visible semester
    url = reverse("courses:course_list", kwargs={"slug": newer_visible.slug})
    response = client.get(url)

    # Previous semester should include the invisible one
    assert response.context["prev_semester"] == middle_invisible
    assert response.context["next_semester"] is None

    # Access the middle invisible semester
    url = reverse("courses:course_list", kwargs={"slug": middle_invisible.slug})
    response = client.get(url)

    # Should see both neighbors
    assert response.context["prev_semester"] == older_visible
    assert response.context["next_semester"] == newer_visible
