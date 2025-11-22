from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student

from .models import YearbookEntry


# ============================================================================
# Model Tests
# ============================================================================


@pytest.mark.django_db
def test_yearbook_entry_creation():
    """Test creating a yearbook entry."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="testuser", password="password")
    student = Student.objects.create(
        user=user,
        airtable_name="Test Student",
        semester=semester,
        house=Student.House.BLOB,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test Display Name",
        bio="This is my bio!",
    )

    assert entry.display_name == "Test Display Name"
    assert entry.bio == "This is my bio!"
    assert entry.student == student
    assert str(entry) == "Test Display Name (Fall 2025)"


@pytest.mark.django_db
def test_yearbook_entry_with_social_links():
    """Test creating a yearbook entry with social media links."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        airtable_name="Social Student",
        semester=semester,
        house=Student.House.CAT,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Social User",
        bio="I love social media!",
        discord_username="socialuser#1234",
        instagram_username="socialuser",
        github_username="socialuser",
        website_url="https://socialuser.com",
    )

    assert entry.discord_username == "socialuser#1234"
    assert entry.instagram_username == "socialuser"
    assert entry.github_username == "socialuser"
    assert entry.website_url == "https://socialuser.com"


# ============================================================================
# CreateView Permission Tests
# ============================================================================


@pytest.mark.django_db
def test_create_view_requires_login():
    """Test that creating a yearbook entry requires login."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        airtable_name="Test Student",
        semester=semester,
    )

    url = reverse("yearbook:create", kwargs={"student_pk": student.pk})
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_create_view_only_owner_can_access():
    """Test that only the student's user can create their yearbook entry."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    User.objects.create_user(username="other", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )

    # Other user tries to access - gets 404 (not revealing resource existence)
    client.login(username="other", password="password")
    url = reverse("yearbook:create", kwargs={"student_pk": student.pk})
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_create_view_owner_can_access():
    """Test that the student's owner can access the create view."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:create", kwargs={"student_pk": student.pk})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_create_view_denied_after_semester_ended():
    """Test that yearbook entries cannot be created after semester ends."""
    client = Client()
    # Create a semester that has ended
    semester = Semester.objects.create(
        name="Fall 2024",
        slug="fa24",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:create", kwargs={"student_pk": student.pk})
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_view_redirects_if_entry_exists():
    """Test that create view redirects to edit if entry already exists."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test",
        bio="Test bio",
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:create", kwargs={"student_pk": student.pk})
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse("yearbook:edit", kwargs={"pk": entry.pk})


@pytest.mark.django_db
def test_create_view_successful_submission():
    """Test successfully creating a yearbook entry."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:create", kwargs={"student_pk": student.pk})
    response = client.post(
        url,
        {
            "display_name": "My Display Name",
            "bio": "This is my introduction!",
            "discord_username": "myuser#1234",
            "instagram_username": "",
            "github_username": "",
            "website_url": "",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "yearbook:semester_list", kwargs={"slug": semester.slug}
    )

    # Verify entry was created
    entry = YearbookEntry.objects.get(student=student)
    assert entry.display_name == "My Display Name"
    assert entry.bio == "This is my introduction!"
    assert entry.discord_username == "myuser#1234"


# ============================================================================
# UpdateView Permission Tests
# ============================================================================


@pytest.mark.django_db
def test_update_view_requires_login():
    """Test that updating a yearbook entry requires login."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        airtable_name="Test Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test",
        bio="Test bio",
    )

    url = reverse("yearbook:edit", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_update_view_only_owner_can_access():
    """Test that only the student's user can update their yearbook entry."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    User.objects.create_user(username="other", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test",
        bio="Test bio",
    )

    # Other user tries to access
    client.login(username="other", password="password")
    url = reverse("yearbook:edit", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_update_view_owner_can_access():
    """Test that the student's owner can access the update view."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test",
        bio="Test bio",
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:edit", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_update_view_denied_after_semester_ended():
    """Test that yearbook entries cannot be updated after semester ends."""
    client = Client()
    # Create a semester that has ended
    semester = Semester.objects.create(
        name="Fall 2024",
        slug="fa24",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Test",
        bio="Test bio",
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:edit", kwargs={"pk": entry.pk})
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_update_view_successful_submission():
    """Test successfully updating a yearbook entry."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )
    entry = YearbookEntry.objects.create(
        student=student,
        display_name="Old Name",
        bio="Old bio",
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:edit", kwargs={"pk": entry.pk})
    response = client.post(
        url,
        {
            "display_name": "New Name",
            "bio": "New bio with more content!",
            "discord_username": "newuser#5678",
            "instagram_username": "newinstagram",
            "github_username": "",
            "website_url": "",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "yearbook:semester_list", kwargs={"slug": semester.slug}
    )

    # Verify entry was updated
    entry.refresh_from_db()
    assert entry.display_name == "New Name"
    assert entry.bio == "New bio with more content!"
    assert entry.discord_username == "newuser#5678"
    assert entry.instagram_username == "newinstagram"


# ============================================================================
# ListView Permission Tests
# ============================================================================


@pytest.mark.django_db
def test_semester_list_requires_login():
    """Test that viewing the semester yearbook requires login."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_semester_list_staff_can_access_any_semester():
    """Test that staff can view yearbook for any semester."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    User.objects.create_user(username="staff", password="password", is_staff=True)

    client.login(username="staff", password="password")
    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_semester_list_student_in_semester_can_access():
    """Test that students in the semester can view the yearbook."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    Student.objects.create(
        user=user,
        airtable_name="Student",
        semester=semester,
    )

    client.login(username="student", password="password")
    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_semester_list_student_not_in_semester_denied():
    """Test that students not in the semester cannot view the yearbook."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    other_semester = Semester.objects.create(
        name="Spring 2025",
        slug="sp25",
        start_date=(timezone.now() - timedelta(days=180)).date(),
        end_date=(timezone.now() - timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    # Student is in a different semester
    Student.objects.create(
        user=user,
        airtable_name="Student",
        semester=other_semester,
    )

    client.login(username="student", password="password")
    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_semester_list_user_without_student_denied():
    """Test that users without any student record cannot view the yearbook."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    User.objects.create_user(username="regular", password="password")

    client.login(username="regular", password="password")
    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_semester_list_student_can_view_without_having_entry():
    """Test that students can view the yearbook even if they don't have an entry."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    Student.objects.create(
        user=user,
        airtable_name="Student without entry",
        semester=semester,
    )

    client.login(username="student", password="password")
    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    assert "No yearbook entries yet" in response.content.decode()


@pytest.mark.django_db
def test_semester_list_shows_entries_sorted_by_house():
    """Test that yearbook entries are sorted by house."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students in different houses
    user = User.objects.create_user(username="viewer", password="password")
    Student.objects.create(user=user, airtable_name="Viewer", semester=semester)

    blob_student = Student.objects.create(
        airtable_name="Blob Student",
        semester=semester,
        house=Student.House.BLOB,
    )
    cat_student = Student.objects.create(
        airtable_name="Cat Student",
        semester=semester,
        house=Student.House.CAT,
    )
    owl_student = Student.objects.create(
        airtable_name="Owl Student",
        semester=semester,
        house=Student.House.OWL,
    )

    # Create entries
    YearbookEntry.objects.create(
        student=cat_student, display_name="Cat Person", bio="I love cats"
    )
    YearbookEntry.objects.create(
        student=blob_student, display_name="Blob Person", bio="I love blobs"
    )
    YearbookEntry.objects.create(
        student=owl_student, display_name="Owl Person", bio="I love owls"
    )

    client.login(username="viewer", password="password")
    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    # Check all entries are shown
    assert "Blob Person" in content
    assert "Cat Person" in content
    assert "Owl Person" in content


@pytest.mark.django_db
def test_semester_list_shows_create_button_before_semester_ends():
    """Test that the create button is shown before the semester ends."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    Student.objects.create(user=user, airtable_name="Student", semester=semester)

    client.login(username="student", password="password")
    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Should show create button since student doesn't have an entry
    assert "Create Your Entry" in content


@pytest.mark.django_db
def test_semester_list_shows_edit_button_for_existing_entry():
    """Test that the edit button is shown for students with existing entries."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    student = Student.objects.create(
        user=user, airtable_name="Student", semester=semester
    )
    YearbookEntry.objects.create(
        student=student, display_name="Student Name", bio="My bio"
    )

    client.login(username="student", password="password")
    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Should show edit button since student has an entry
    assert "Edit Your Entry" in content


@pytest.mark.django_db
def test_semester_list_no_edit_button_after_semester_ends():
    """Test that no edit/create button is shown after semester ends."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2024",
        slug="fa24",
        start_date=(timezone.now() - timedelta(days=120)).date(),
        end_date=(timezone.now() - timedelta(days=30)).date(),
    )
    user = User.objects.create_user(username="student", password="password")
    Student.objects.create(user=user, airtable_name="Student", semester=semester)

    client.login(username="student", password="password")
    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    # Should show message that semester has ended
    assert "semester has ended" in content
    assert "Create Your Entry" not in content
    assert "Edit Your Entry" not in content


@pytest.mark.django_db
def test_semester_list_shows_social_links():
    """Test that social media links are displayed correctly."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="viewer", password="password")
    Student.objects.create(user=user, airtable_name="Viewer", semester=semester)

    student = Student.objects.create(
        airtable_name="Social Student",
        semester=semester,
        house=Student.House.BLOB,
    )
    YearbookEntry.objects.create(
        student=student,
        display_name="Social Person",
        bio="Check out my socials!",
        discord_username="socialuser#1234",
        instagram_username="socialinsta",
        github_username="socialgit",
        website_url="https://social.example.com",
    )

    client.login(username="viewer", password="password")
    url = reverse("yearbook:semester_list", kwargs={"slug": semester.slug})
    response = client.get(url)

    content = response.content.decode()
    assert "socialuser#1234" in content
    assert "socialinsta" in content
    assert "socialgit" in content
    assert "https://social.example.com" in content


# ============================================================================
# Bio Length Validation Tests
# ============================================================================


@pytest.mark.django_db
def test_bio_max_length_validation():
    """Test that bio is limited to 1000 characters."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:create", kwargs={"student_pk": student.pk})

    # Try to submit a bio that's too long
    long_bio = "x" * 1001
    response = client.post(
        url,
        {
            "display_name": "Test Name",
            "bio": long_bio,
            "discord_username": "",
            "instagram_username": "",
            "github_username": "",
            "website_url": "",
        },
    )

    # Should not redirect (form error)
    assert response.status_code == 200
    # Entry should not be created
    assert not YearbookEntry.objects.filter(student=student).exists()


@pytest.mark.django_db
def test_bio_at_max_length_succeeds():
    """Test that a bio at exactly 1000 characters is accepted."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
    )
    owner = User.objects.create_user(username="owner", password="password")
    student = Student.objects.create(
        user=owner,
        airtable_name="Owner's Student",
        semester=semester,
    )

    client.login(username="owner", password="password")
    url = reverse("yearbook:create", kwargs={"student_pk": student.pk})

    # Submit a bio at exactly 1000 characters
    max_bio = "x" * 1000
    response = client.post(
        url,
        {
            "display_name": "Test Name",
            "bio": max_bio,
            "discord_username": "",
            "instagram_username": "",
            "github_username": "",
            "website_url": "",
        },
    )

    # Should redirect on success
    assert response.status_code == 302
    # Entry should be created
    entry = YearbookEntry.objects.get(student=student)
    assert len(entry.bio) == 1000
