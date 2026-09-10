"""
One-time command to re-encode uploaded images down to the size they display at.

Uploads made before DownscaledImageField was introduced are stored at whatever
resolution the camera or screenshot produced. This rewrites them through the
same helper new uploads go through, reading each field's target size off the
field itself.

A file keeps its name whenever the format is unchanged, which weblog photos
depend on: their URLs are pasted into post markdown and one is hardcoded in a
template. Where the extension has to change, the row is repointed at the new
file and the old one is deleted afterwards, so an interrupted run leaves
earlier rows rewritten and later ones untouched; re-running finishes the job.

Files are rewritten under MEDIA_ROOT with no backup, so take one first and use
--dry-run before the real thing.
"""

from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db.models import Model
from PIL import UnidentifiedImageError

from atheweb.fields import DownscaledImageField
from atheweb.images import downscale, needs_downscaling
from home.models import StaffPhotoListing
from weblog.models import Photo

TARGETS: list[tuple[type[Model], str]] = [
    (StaffPhotoListing, "photo"),
    (Photo, "image"),
]


def format_bytes(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / 1024:.0f} KB"


class Command(BaseCommand):
    help = "Re-encode uploaded images down to the size they display at"

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without rewriting anything",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN - no files will be rewritten")
            )

        rewritten = 0
        bytes_saved = 0

        for model, field_name in TARGETS:
            field = model._meta.get_field(field_name)
            assert isinstance(field, DownscaledImageField)
            self.stdout.write(f"{model._meta.verbose_name_plural}:")

            for instance in model.objects.exclude(**{field_name: ""}):
                saved = self.rewrite(
                    getattr(instance, field_name), field, str(instance), dry_run
                )
                if saved:
                    rewritten += 1
                    bytes_saved += saved

        if not rewritten:
            self.stdout.write(self.style.SUCCESS("Every image is already small"))
            return

        verb = "would save" if dry_run else "saved"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{rewritten} image(s) rewritten, {verb} {format_bytes(bytes_saved)}"
            )
        )

    def rewrite(
        self,
        image: Any,
        field: DownscaledImageField,
        label: str,
        dry_run: bool,
    ) -> int:
        """Shrink one stored image, returning the bytes saved (0 if skipped)."""
        if not image.storage.exists(image.name):
            self.stderr.write(
                self.style.WARNING(f"  {label}: {image.name} is missing, skipping")
            )
            return 0

        try:
            with image.open("rb") as f:
                if not needs_downscaling(f, field.max_dimension, field.to_jpeg):
                    return 0
                f.seek(0)
                replacement = downscale(
                    f, image.name, field.max_dimension, field.to_jpeg
                )
        except (ValidationError, UnidentifiedImageError, OSError) as e:
            self.stderr.write(self.style.WARNING(f"  {label}: {e}"))
            return 0

        before = image.size
        if replacement.size >= before:
            return 0

        self.stdout.write(
            f"  {label}: {format_bytes(before)} -> {format_bytes(replacement.size)}"
        )
        if dry_run:
            return before - replacement.size

        old_name = image.name
        if replacement.name == old_name.rsplit("/", 1)[-1]:
            image.storage.delete(old_name)
            image.storage.save(old_name, replacement)
        else:
            image.save(replacement.name, replacement, save=True)
            image.storage.delete(old_name)

        return before - replacement.size
