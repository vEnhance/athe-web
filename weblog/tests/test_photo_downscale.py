import pytest
from django.forms import modelform_factory
from PIL import Image

from atheweb.images import CONTENT_MAX_DIMENSION
from home.tests.test_staff_photo_downscale import upload
from weblog.models import Photo

PhotoForm = modelform_factory(Photo, fields=["name", "image"])


def submit(image) -> Photo:
    """Upload through a ModelForm, the way the admin does."""
    form = PhotoForm({"name": "Test"}, {"image": image})
    assert form.is_valid(), form.errors
    return form.save()


@pytest.mark.django_db
def test_oversized_content_photo_is_downscaled():
    """A big screenshot is capped, but at a far larger box than a headshot."""
    photo = submit(upload(4000, 3000, fmt="PNG"))
    with photo.image.open("rb") as f, Image.open(f) as image:
        assert max(image.size) == CONTENT_MAX_DIMENSION


@pytest.mark.django_db
def test_png_stays_png():
    """Screenshots keep their format, so text does not pick up JPEG artifacts."""
    photo = submit(upload(3000, 2000, fmt="PNG"))
    assert photo.image.name.endswith(".png")
    with photo.image.open("rb") as f, Image.open(f) as image:
        assert image.format == "PNG"


@pytest.mark.django_db
def test_jpeg_stays_jpeg():
    """A photographic upload is not converted to PNG."""
    photo = submit(upload(3000, 2000))
    assert photo.image.name.endswith(".jpg")
    with photo.image.open("rb") as f, Image.open(f) as image:
        assert image.format == "JPEG"


@pytest.mark.django_db
def test_photo_under_the_cap_is_untouched():
    """A blog-sized image is left at its original resolution."""
    photo = submit(upload(1200, 800, fmt="PNG"))
    with photo.image.open("rb") as f, Image.open(f) as image:
        assert image.size == (1200, 800)


@pytest.mark.django_db
def test_gif_is_left_alone():
    """A GIF is stored untouched rather than flattened or renamed."""
    photo = submit(upload(3000, 2000, fmt="GIF"))
    assert photo.image.name.endswith(".gif")
    with photo.image.open("rb") as f, Image.open(f) as image:
        assert image.format == "GIF"
        assert image.size == (3000, 2000)
