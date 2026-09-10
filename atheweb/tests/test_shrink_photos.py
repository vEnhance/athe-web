from io import StringIO

import pytest
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management import call_command
from PIL import Image

from atheweb.images import CONTENT_MAX_DIMENSION, STAFF_MAX_DIMENSION
from home.models import StaffPhotoListing
from home.tests.test_staff_photo_downscale import upload
from weblog.models import Photo


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
    call_command("shrink_photos", *args, stdout=out, stderr=StringIO())
    return out.getvalue()


def stored_size(fieldfile) -> tuple[int, int]:
    with fieldfile.open("rb") as f, Image.open(f) as image:
        return image.size


@pytest.mark.django_db
def test_oversized_staff_photo_is_rewritten():
    """A big staff photo is shrunk to the box it displays in."""
    staff = make_listing("big", upload(1600, 1200))
    before = staff.photo.size

    shrink()

    staff.refresh_from_db()
    assert max(stored_size(staff.photo)) == STAFF_MAX_DIMENSION
    assert staff.photo.size < before


@pytest.mark.django_db
def test_staff_jpeg_keeps_its_name():
    """Nothing is renamed when the extension does not have to change."""
    staff = make_listing("big", upload(1600, 1200))
    old_name = staff.photo.name

    shrink()

    staff.refresh_from_db()
    assert staff.photo.name == old_name


@pytest.mark.django_db
def test_staff_png_is_renamed_and_the_old_file_removed():
    """Converting to JPEG changes the extension, so the row is repointed."""
    staff = make_listing("png", upload(1600, 1200, fmt="PNG"))
    old_name = staff.photo.name

    shrink()

    staff.refresh_from_db()
    assert staff.photo.name.endswith(".jpg")
    assert staff.photo.name != old_name
    assert not staff.photo.storage.exists(old_name)


@pytest.mark.django_db
def test_weblog_photo_is_rewritten_in_place():
    """A weblog photo keeps its name; post markdown references it by URL."""
    photo = Photo.objects.create(name="Screenshot", image=upload(3000, 2000, fmt="PNG"))
    old_name = photo.image.name
    before = photo.image.size

    shrink()

    photo.refresh_from_db()
    assert photo.image.name == old_name
    assert photo.markdown_url == f"/media/{old_name}"
    assert photo.image.size < before


@pytest.mark.django_db
def test_weblog_photo_keeps_its_format_and_larger_cap():
    """Content images stay PNG and are allowed to be much bigger than headshots."""
    photo = Photo.objects.create(name="Diagram", image=upload(3000, 2000, fmt="PNG"))

    shrink()

    photo.refresh_from_db()
    assert max(stored_size(photo.image)) == CONTENT_MAX_DIMENSION
    with photo.image.open("rb") as f, Image.open(f) as image:
        assert image.format == "PNG"


@pytest.mark.django_db
def test_already_small_images_are_left_alone():
    """Small files are not re-encoded, so no quality is lost."""
    staff = make_listing("small", upload(200, 200))
    photo = Photo.objects.create(name="Small", image=upload(400, 300, fmt="PNG"))
    sizes = (staff.photo.size, photo.image.size)

    assert "Nothing left to rewrite" in shrink()

    staff.refresh_from_db()
    photo.refresh_from_db()
    assert (staff.photo.size, photo.image.size) == sizes


@pytest.mark.django_db
def test_second_run_finds_nothing_to_do():
    """The command is idempotent."""
    make_listing("big", upload(1600, 1200))
    Photo.objects.create(name="Big", image=upload(3000, 2000, fmt="PNG"))
    shrink()
    assert "Nothing left to rewrite" in shrink()


@pytest.mark.django_db
def test_dry_run_changes_nothing():
    """--dry-run reports the saving without rewriting anything."""
    staff = make_listing("big", upload(1600, 1200))
    old_name = staff.photo.name

    assert "would save" in shrink("--dry-run")

    staff.refresh_from_db()
    assert staff.photo.name == old_name
    assert stored_size(staff.photo) == (1600, 1200)


@pytest.mark.django_db
def test_missing_file_is_skipped():
    """A row pointing at a file that isn't there does not crash the run."""
    make_listing("gone", "staff_photos/nope.jpg")
    make_listing("big", upload(1600, 1200))

    assert "big" in shrink()


def seed_every_outcome() -> None:
    """Store one image per outcome the command can report."""
    make_listing("oversized", upload(1600, 1200))
    make_listing("in-spec", upload(200, 200))
    make_listing("no-gain", upload(40, 40, fmt="PNG"))
    make_listing("gone", "staff_photos/nope.jpg")
    make_listing("bogus", "staff_photos/bogus.jpg")
    default_storage.save("staff_photos/bogus.jpg", ContentFile(b"not an image"))
    Photo.objects.create(name="Screenshot", image=upload(3000, 2000, fmt="PNG"))
    Photo.objects.create(name="Animation", image=upload(900, 600, fmt="GIF"))


EXPECTED = {
    "2 would rewrite": "the oversized JPEG and the oversized PNG",
    "1 already the right size": "the in-spec JPEG",
    "1 format left as is": "the GIF",
    "1 no smaller re-encoded": "the tiny PNG",
    "1 file missing": "the row pointing at nothing",
    "1 unreadable": "the file that is not an image",
}


@pytest.mark.django_db
def test_dry_run_reports_every_outcome():
    """The breakdown accounts for every stored image, not just the rewritten ones."""
    seed_every_outcome()

    report = shrink("--dry-run")

    for line, description in EXPECTED.items():
        assert line in report, f"missing {description}: {line}"


@pytest.mark.django_db
def test_real_run_counts_match_the_dry_run():
    """The two paths classify identically, so they cannot drift."""
    seed_every_outcome()

    report = shrink()

    for line in EXPECTED:
        assert line.replace("would rewrite", "rewritten") in report


@pytest.mark.django_db
def test_breakdown_explains_a_second_run():
    """After a real run the images are accounted for as already the right size."""
    make_listing("oversized", upload(1600, 1200))
    shrink()

    report = shrink()

    assert "1 already the right size" in report
    assert "Nothing left to rewrite" in report
