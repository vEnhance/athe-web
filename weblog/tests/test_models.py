from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from weblog.models import HistoryEntry, Photo


def create_test_image():
    """Create a test image for photo model."""
    image = Image.new("RGB", (100, 100), color="blue")
    image_io = BytesIO()
    image.save(image_io, format="JPEG")
    image_io.seek(0)
    return SimpleUploadedFile(
        name="test_photo.jpg",
        content=image_io.getvalue(),
        content_type="image/jpeg",
    )


# ============================================================================
# Photo Model Tests
# ============================================================================


@pytest.mark.django_db
def test_photo_creation():
    """Test creating a Photo model."""
    photo = Photo.objects.create(
        name="Test Photo",
        image=create_test_image(),
    )
    assert photo.name == "Test Photo"
    assert photo.id is not None
    assert photo.uploaded_at is not None


@pytest.mark.django_db
def test_photo_str():
    """Test the string representation of Photo."""
    photo = Photo.objects.create(
        name="My Photo",
        image=create_test_image(),
    )
    assert str(photo) == "My Photo"


@pytest.mark.django_db
def test_photo_markdown_url():
    """Test the markdown_url property."""
    photo = Photo.objects.create(
        name="Test Photo",
        image=create_test_image(),
    )
    assert photo.markdown_url.startswith("/media/photos/")
    assert "test_photo" in photo.markdown_url


@pytest.mark.django_db
def test_photo_ordering():
    """Test that photos are ordered by uploaded_at descending."""
    photo1 = Photo.objects.create(name="Photo 1", image=create_test_image())
    photo2 = Photo.objects.create(name="Photo 2", image=create_test_image())

    photos = list(Photo.objects.all())
    # Most recent first
    assert photos[0].id == photo2.id
    assert photos[1].id == photo1.id


# ============================================================================
# HistoryEntry Model Tests
# ============================================================================


@pytest.mark.django_db
def test_history_entry_creation():
    """Test creating a HistoryEntry."""
    entry = HistoryEntry.objects.create(
        title="The Beginning",
        slug="the-beginning",
        content="This is where it all started.",
        visible=True,
    )
    assert entry.title == "The Beginning"
    assert entry.slug == "the-beginning"
    assert entry.visible is True
    assert entry.id is not None
    assert entry.created_at is not None


@pytest.mark.django_db
def test_history_entry_str():
    """Test the string representation of HistoryEntry."""
    entry = HistoryEntry.objects.create(
        title="A Historical Event",
        slug="a-historical-event",
        content="Something happened.",
    )
    assert str(entry) == "A Historical Event"


@pytest.mark.django_db
def test_history_entry_default_visible():
    """Test that HistoryEntry is visible by default."""
    entry = HistoryEntry.objects.create(
        title="Default Entry",
        slug="default-entry",
        content="Default content.",
    )
    assert entry.visible is True


@pytest.mark.django_db
def test_history_entry_invisible():
    """Test creating an invisible HistoryEntry."""
    entry = HistoryEntry.objects.create(
        title="Hidden Entry",
        slug="hidden-entry",
        content="This is hidden.",
        visible=False,
    )
    assert entry.visible is False


@pytest.mark.django_db
def test_history_entry_slug_unique():
    """Test that HistoryEntry slugs must be unique."""
    HistoryEntry.objects.create(
        title="First Entry",
        slug="unique-slug",
        content="First content.",
    )

    # Creating another entry with the same slug should raise an error
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        HistoryEntry.objects.create(
            title="Second Entry",
            slug="unique-slug",
            content="Second content.",
        )


@pytest.mark.django_db
def test_history_entry_ordering():
    """Test that history entries are ordered by created_at descending."""
    entry1 = HistoryEntry.objects.create(
        title="Older Entry",
        slug="older-entry",
        content="Older content.",
    )
    entry2 = HistoryEntry.objects.create(
        title="Newer Entry",
        slug="newer-entry",
        content="Newer content.",
    )

    entries = list(HistoryEntry.objects.all())
    # Most recent first
    assert entries[0].id == entry2.id
    assert entries[1].id == entry1.id


@pytest.mark.django_db
def test_history_entry_markdown_rendering():
    """Test that markdown content is rendered to HTML."""
    entry = HistoryEntry.objects.create(
        title="Markdown Test",
        slug="markdown-test",
        content="**Bold text** and *italic text*",
    )
    # The content_rendered field should contain HTML
    assert "<strong>" in entry.content_rendered or "<b>" in entry.content_rendered
    assert "<em>" in entry.content_rendered or "<i>" in entry.content_rendered
