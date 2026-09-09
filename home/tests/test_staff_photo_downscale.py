from io import BytesIO

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse
from PIL import Image

from atheweb import fields, images
from atheweb.images import MAX_DIMENSION
from home.models import StaffPhotoListing


def upload(width: int, height: int, fmt: str = "JPEG", **save_kwargs: object):
    """Build an uploadable image of the given size."""
    mode = "RGBA" if fmt == "PNG" else "RGB"
    image = Image.new(mode, (width, height), color="red")
    buffer = BytesIO()
    image.save(buffer, format=fmt, **save_kwargs)
    return SimpleUploadedFile(
        name=f"headshot.{fmt.lower()}",
        content=buffer.getvalue(),
        content_type=f"image/{fmt.lower()}",
    )


def edit_as_owner(client: Client, photo=None) -> tuple[StaffPhotoListing, int]:
    """Post the staff edit form for a fresh listing; return it and the status."""
    user = User.objects.create_user(username="staffuser", password="testpass")
    staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Staff User",
        slug="staff-user",
        role="Instructor",
        category="instructor",
        biography="A staff member.",
        photo=upload(60, 60),
    )
    client.login(username="staffuser", password="testpass")
    data = {"display_name": "Staff User", "biography": "A staff member."}
    if photo is not None:
        data["photo"] = photo
    response = client.post(reverse("home:staff_edit"), data)
    staff.refresh_from_db()
    return staff, response.status_code


@pytest.mark.django_db
def test_large_upload_is_downscaled():
    """A big upload is stored no larger than the box it displays in."""
    staff, _ = edit_as_owner(Client(), upload(2000, 1500))
    assert max(staff.photo.width, staff.photo.height) == MAX_DIMENSION
    assert staff.photo.width / staff.photo.height == pytest.approx(
        2000 / 1500, abs=0.01
    )
    assert staff.photo.size < 200_000


@pytest.mark.django_db
def test_png_upload_is_stored_as_jpeg():
    """Transparency is flattened and the stored file is a JPEG."""
    staff, _ = edit_as_owner(Client(), upload(1200, 1200, fmt="PNG"))
    assert staff.photo.name.endswith(".jpg")
    with staff.photo.open("rb") as f, Image.open(f) as image:
        assert image.format == "JPEG"


@pytest.mark.django_db
def test_small_upload_is_not_upscaled():
    """An already-small photo keeps its dimensions."""
    staff, _ = edit_as_owner(Client(), upload(100, 80))
    assert (staff.photo.width, staff.photo.height) == (100, 80)


@pytest.mark.django_db
def test_exif_orientation_is_applied():
    """A sideways phone photo is stored the right way up."""
    exif = Image.Exif()
    exif[274] = 6  # Orientation: rotate 270
    staff, _ = edit_as_owner(Client(), upload(400, 200, exif=exif.tobytes()))
    assert (staff.photo.width, staff.photo.height) == (200, 400)


@pytest.mark.django_db
def test_oversized_upload_is_rejected(monkeypatch: pytest.MonkeyPatch):
    """A file over the byte cap is refused instead of being processed."""
    monkeypatch.setattr(fields, "MAX_UPLOAD_BYTES", 100)
    client = Client()
    staff, status = edit_as_owner(client, upload(2000, 1500))
    assert status == 200
    assert (staff.photo.width, staff.photo.height) == (60, 60)


@pytest.mark.django_db
def test_absurd_pixel_count_is_refused(monkeypatch: pytest.MonkeyPatch):
    """A decompression bomb becomes a form error, not a jail-killing decode."""
    monkeypatch.setattr(images, "MAX_PIXELS", 100)
    client = Client()
    staff, status = edit_as_owner(client, upload(400, 300))
    assert status == 200
    assert (staff.photo.width, staff.photo.height) == (60, 60)


@pytest.mark.django_db
def test_edit_without_new_photo_keeps_the_existing_one():
    """Saving other fields does not re-encode or drop the photo."""
    client = Client()
    user = User.objects.create_user(username="staffuser", password="testpass")
    staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Staff User",
        slug="staff-user",
        role="Instructor",
        category="instructor",
        biography="A staff member.",
        photo=upload(300, 300),
    )
    original_name = staff.photo.name
    client.login(username="staffuser", password="testpass")
    response = client.post(
        reverse("home:staff_edit"),
        {"display_name": "Renamed", "biography": "A staff member."},
    )
    assert response.status_code == 302
    staff.refresh_from_db()
    assert staff.display_name == "Renamed"
    assert staff.photo.name == original_name


@pytest.mark.django_db
def test_staff_list_defers_offscreen_photos():
    """The staff grid renders every listing at once, so its photos load lazily."""
    StaffPhotoListing.objects.create(
        display_name="Listed",
        slug="listed",
        role="Instructor",
        category="instructor",
        biography="Bio",
        photo=upload(60, 60),
    )
    content = Client().get(reverse("home:staff")).content.decode()
    assert 'class="staff-img"' in content
    assert 'loading="lazy"' in content
