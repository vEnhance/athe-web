from io import StringIO

import pytest
from django.core.management import call_command
from PIL import Image

from atheweb.images import MAX_DIMENSION
from home.models import StaffPhotoListing
from home.tests.test_staff_photo_downscale import upload


def make_listing(slug: str, photo) -> StaffPhotoListing:
    return StaffPhotoListing.objects.create(
        display_name=slug,
        slug=slug,
        role="Instructor",
        category="instructor",
        biography="Bio",
        photo=photo,
    )


def shrink(*args: str) -> str:
    out = StringIO()
    call_command("shrink_staff_photos", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


@pytest.mark.django_db
def test_oversized_photo_is_rewritten():
    """A big stored photo is shrunk and its old file removed."""
    staff = make_listing("big", upload(1600, 1200))
    old_name = staff.photo.name
    before = staff.photo.size

    shrink()

    staff.refresh_from_db()
    assert staff.photo.name != old_name
    assert not staff.photo.storage.exists(old_name)
    assert max(staff.photo.width, staff.photo.height) == MAX_DIMENSION
    assert staff.photo.size < before


@pytest.mark.django_db
def test_already_small_photo_is_left_alone():
    """A small JPEG is not touched, so no quality is lost to re-encoding."""
    staff = make_listing("small", upload(200, 200))
    old_name = staff.photo.name

    assert "already small" in shrink()

    staff.refresh_from_db()
    assert staff.photo.name == old_name


@pytest.mark.django_db
def test_second_run_finds_nothing_to_do():
    """The command is idempotent."""
    make_listing("big", upload(1600, 1200))
    shrink()
    assert "already small" in shrink()


@pytest.mark.django_db
def test_dry_run_changes_nothing():
    """--dry-run reports the saving without rewriting anything."""
    staff = make_listing("big", upload(1600, 1200))
    old_name = staff.photo.name

    assert "would save" in shrink("--dry-run")

    staff.refresh_from_db()
    assert staff.photo.name == old_name
    with staff.photo.open("rb") as f, Image.open(f) as image:
        assert image.size == (1600, 1200)


@pytest.mark.django_db
def test_missing_file_is_skipped():
    """A listing pointing at a file that isn't there does not crash the run."""
    make_listing("gone", "staff_photos/nope.jpg")
    make_listing("big", upload(1600, 1200))

    assert "big" in shrink()
