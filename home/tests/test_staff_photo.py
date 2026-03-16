from io import BytesIO

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from PIL import Image

from home.models import StaffPhotoListing


def create_test_image():
    """Create a test image for staff photo."""
    image = Image.new("RGB", (100, 100), color="red")
    image_io = BytesIO()
    image.save(image_io, format="JPEG")
    image_io.seek(0)
    return SimpleUploadedFile(
        name="test_photo.jpg",
        content=image_io.getvalue(),
        content_type="image/jpeg",
    )


@pytest.mark.django_db
def test_create_staff_photo_listing():
    """Test creating a StaffPhotoListing with social fields."""
    staff = StaffPhotoListing.objects.create(
        display_name="John Doe",
        slug="john-doe",
        role="Instructor",
        category="instructor",
        biography="A great instructor.",
        photo=create_test_image(),
        website="https://example.com",
        email="john@example.com",
        instagram_username="johndoe",
        discord_username="johndoe#1234",
        github_username="johndoe",
    )
    assert staff.display_name == "John Doe"
    assert staff.website == "https://example.com"
    assert staff.email == "john@example.com"
    assert staff.instagram_username == "johndoe"
    assert staff.discord_username == "johndoe#1234"
    assert staff.github_username == "johndoe"


@pytest.mark.django_db
def test_staff_photo_listing_optional_fields():
    """Test that social fields are optional."""
    staff = StaffPhotoListing.objects.create(
        display_name="Jane Doe",
        slug="jane-doe",
        role="TA",
        category="ta",
        biography="A helpful TA.",
        photo=create_test_image(),
    )
    assert staff.website == ""
    assert staff.email == ""
    assert staff.instagram_username == ""
    assert staff.discord_username == ""
    assert staff.github_username == ""


@pytest.mark.django_db
def test_staff_photo_listing_str():
    """Test string representation of StaffPhotoListing."""
    staff = StaffPhotoListing.objects.create(
        display_name="Test Staff",
        slug="test-staff",
        role="Member",
        category="board",
        biography="Bio",
        photo=create_test_image(),
    )
    assert str(staff) == "Test Staff"


@pytest.mark.django_db
def test_staff_photo_listing_get_absolute_url():
    """Test get_absolute_url returns correct URL."""
    staff = StaffPhotoListing.objects.create(
        display_name="Test Staff",
        slug="test-staff",
        role="Member",
        category="board",
        biography="Bio",
        photo=create_test_image(),
    )
    assert staff.get_absolute_url() == "/staff/test-staff/"


@pytest.mark.django_db
def test_staff_detail_view_displays_social_links():
    """Test that staff detail view displays social links."""
    client = Client()
    staff = StaffPhotoListing.objects.create(
        display_name="Social Staff",
        slug="social-staff",
        role="Instructor",
        category="instructor",
        biography="Has social links.",
        photo=create_test_image(),
        website="https://mywebsite.com",
        email="contact@example.com",
        instagram_username="myinsta",
        discord_username="mydiscord",
        github_username="mygithub",
    )
    response = client.get(reverse("home:staff_detail", kwargs={"slug": staff.slug}))
    assert response.status_code == 200
    content = response.content.decode()
    assert "https://mywebsite.com" in content
    assert "mailto:contact@example.com" in content
    assert "https://instagram.com/myinsta" in content
    assert "mydiscord" in content
    assert "https://github.com/mygithub" in content


@pytest.mark.django_db
def test_staff_detail_view_hides_empty_social_links():
    """Test that staff detail view hides empty social links section."""
    client = Client()
    staff = StaffPhotoListing.objects.create(
        display_name="No Social Staff",
        slug="no-social-staff",
        role="Instructor",
        category="instructor",
        biography="No social links.",
        photo=create_test_image(),
    )
    response = client.get(reverse("home:staff_detail", kwargs={"slug": staff.slug}))
    assert response.status_code == 200
    content = response.content.decode()
    assert "staff-social-links" not in content


@pytest.mark.django_db
def test_staff_edit_view_requires_login():
    """Test that staff edit view requires login."""
    client = Client()
    response = client.get(reverse("home:staff_edit"))
    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_staff_edit_view_requires_staff_listing():
    """Test that staff edit view requires user to have a staff listing."""
    client = Client()
    _user = User.objects.create_user(username="testuser", password="testpass")
    client.login(username="testuser", password="testpass")
    response = client.get(reverse("home:staff_edit"))
    assert response.status_code == 404


@pytest.mark.django_db
def test_staff_edit_view_accessible_by_owner():
    """Test that staff edit view is accessible by the staff listing owner."""
    client = Client()
    user = User.objects.create_user(username="staffuser", password="testpass")
    _staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Staff User",
        slug="staff-user",
        role="Instructor",
        category="instructor",
        biography="A staff member.",
        photo=create_test_image(),
    )
    client.login(username="staffuser", password="testpass")
    response = client.get(reverse("home:staff_edit"))
    assert response.status_code == 200
    assert "Edit Your Staff Profile" in response.content.decode()


@pytest.mark.django_db
def test_staff_edit_view_displays_social_fields():
    """Test that staff edit view displays social link fields."""
    client = Client()
    user = User.objects.create_user(username="staffuser", password="testpass")
    _staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Staff User",
        slug="staff-user",
        role="Instructor",
        category="instructor",
        biography="A staff member.",
        photo=create_test_image(),
    )
    client.login(username="staffuser", password="testpass")
    response = client.get(reverse("home:staff_edit"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "website" in content.lower()
    assert "email" in content.lower()
    assert "instagram" in content.lower()
    assert "discord" in content.lower()
    assert "github" in content.lower()


@pytest.mark.django_db
def test_staff_edit_view_updates_social_fields():
    """Test that staff edit view can update social fields."""
    client = Client()
    user = User.objects.create_user(username="staffuser", password="testpass")
    staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Staff User",
        slug="staff-user",
        role="Instructor",
        category="instructor",
        biography="A staff member.",
        photo=create_test_image(),
    )
    client.login(username="staffuser", password="testpass")
    response = client.post(
        reverse("home:staff_edit"),
        {
            "display_name": "Updated Staff",
            "biography": "Updated bio.",
            "website": "https://newwebsite.com",
            "email": "new@example.com",
            "instagram_username": "newinsta",
            "discord_username": "newdiscord",
            "github_username": "newgithub",
        },
    )
    assert response.status_code == 302
    staff.refresh_from_db()
    assert staff.display_name == "Updated Staff"
    assert staff.website == "https://newwebsite.com"
    assert staff.email == "new@example.com"
    assert staff.instagram_username == "newinsta"
    assert staff.discord_username == "newdiscord"
    assert staff.github_username == "newgithub"


@pytest.mark.django_db
def test_staff_view_displays_staff_list():
    """Test that staff view displays staff members."""
    client = Client()
    _staff = StaffPhotoListing.objects.create(
        display_name="Test Instructor",
        slug="test-instructor",
        role="Math Teacher",
        category="instructor",
        biography="Teaches math.",
        photo=create_test_image(),
    )
    response = client.get(reverse("home:staff"))
    assert response.status_code == 200
    assert "Test Instructor" in response.content.decode()


@pytest.mark.django_db
def test_past_staff_view_displays_past_staff():
    """Test that past staff view displays past staff members."""
    client = Client()
    _staff = StaffPhotoListing.objects.create(
        display_name="Former Staff",
        slug="former-staff",
        role="Former Teacher",
        category="xstaff",
        biography="Used to teach.",
        photo=create_test_image(),
    )
    response = client.get(reverse("home:past_staff"))
    assert response.status_code == 200
    assert "Former Staff" in response.content.decode()
