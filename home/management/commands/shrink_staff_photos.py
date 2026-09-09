"""
Management command to re-encode existing staff photos down to display size.

Staff photos are only ever shown in a 200px slot, but uploads predating
DownscaledImageField are stored at whatever resolution the camera produced.
This rewrites them through the same helper new uploads go through.

Each listing is saved and then has its old file deleted, so an interrupted run
leaves earlier listings shrunk and later ones untouched; re-running finishes
the job. Files are rewritten under MEDIA_ROOT with no backup, so take one
first.
"""

from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from PIL import UnidentifiedImageError

from atheweb.images import downscale_to_jpeg, needs_downscaling
from home.models import StaffPhotoListing


def format_bytes(size: int) -> str:
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / 1024:.0f} KB"


class Command(BaseCommand):
    help = "Re-encode existing staff photos down to the size they display at"

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

        shrunk = 0
        bytes_saved = 0

        for listing in StaffPhotoListing.objects.exclude(photo=""):
            photo = listing.photo
            if not photo.storage.exists(photo.name):
                self.stderr.write(
                    self.style.WARNING(f"{listing}: {photo.name} is missing, skipping")
                )
                continue

            try:
                with photo.open("rb") as f:
                    if not needs_downscaling(f):
                        continue
                    f.seek(0)
                    replacement = downscale_to_jpeg(f, photo.name)
            except (ValidationError, UnidentifiedImageError, OSError) as e:
                self.stderr.write(self.style.WARNING(f"{listing}: {e}"))
                continue

            before = photo.size
            after = replacement.size
            if after >= before:
                continue

            self.stdout.write(
                f"  {listing}: {format_bytes(before)} -> {format_bytes(after)}"
            )
            shrunk += 1
            bytes_saved += before - after

            if dry_run:
                continue

            old_name = photo.name
            photo.save(replacement.name, replacement, save=True)
            if photo.name != old_name:
                photo.storage.delete(old_name)

        if not shrunk:
            self.stdout.write(self.style.SUCCESS("Every staff photo is already small"))
            return

        verb = "would save" if dry_run else "saved"
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{shrunk} photo(s) rewritten, {verb} {format_bytes(bytes_saved)}"
            )
        )
