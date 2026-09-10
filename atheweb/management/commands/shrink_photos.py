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

from collections import Counter
from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.db.models import Model
from PIL import UnidentifiedImageError

from atheweb.fields import DownscaledImageField
from atheweb.images import Verdict, classify, downscale
from home.models import StaffPhotoListing
from weblog.models import Photo

NO_GAIN = "no smaller re-encoded"
MISSING = "file missing"
UNREADABLE = "unreadable"

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

        done = "would rewrite" if dry_run else "rewritten"
        outcomes: Counter[str] = Counter()
        bytes_saved = 0

        for model, field_name in TARGETS:
            field = model._meta.get_field(field_name)
            assert isinstance(field, DownscaledImageField)
            lines: list[str] = []

            for instance in model.objects.exclude(**{field_name: ""}):
                outcome, saved = self.rewrite(
                    getattr(instance, field_name), field, str(instance), dry_run, lines
                )
                outcomes[done if outcome is Verdict.REWRITE else outcome] += 1
                bytes_saved += saved

            if lines:
                self.stdout.write(f"{model._meta.verbose_name_plural}:")
                for line in lines:
                    self.stdout.write(line)

        self.stdout.write("")
        for outcome in [done, *sorted(o for o in outcomes if o != done)]:
            if outcomes[outcome]:
                self.stdout.write(f"{outcomes[outcome]:>4} {outcome}")

        if not outcomes[done]:
            self.stdout.write(self.style.SUCCESS("Nothing left to rewrite"))
            return

        verb = "would save" if dry_run else "saved"
        self.stdout.write(self.style.SUCCESS(f"{verb} {format_bytes(bytes_saved)}"))

    def rewrite(
        self,
        image: Any,
        field: DownscaledImageField,
        label: str,
        dry_run: bool,
        lines: list[str],
    ) -> tuple[str, int]:
        """Shrink one stored image, returning its outcome and the bytes saved."""
        if not image.storage.exists(image.name):
            self.stderr.write(
                self.style.WARNING(f"  {label}: {image.name} is missing, skipping")
            )
            return MISSING, 0

        try:
            with image.open("rb") as f:
                verdict = classify(f, field.max_dimension, field.to_jpeg)
                if verdict is not Verdict.REWRITE:
                    return verdict, 0
                f.seek(0)
                replacement = downscale(
                    f, image.name, field.max_dimension, field.to_jpeg
                )
        except (ValidationError, UnidentifiedImageError, OSError) as e:
            self.stderr.write(self.style.WARNING(f"  {label}: {e}"))
            return UNREADABLE, 0

        before = image.size
        if replacement.size >= before:
            return NO_GAIN, 0

        lines.append(
            f"  {label}: {format_bytes(before)} -> {format_bytes(replacement.size)}"
        )
        if dry_run:
            return Verdict.REWRITE, before - replacement.size

        old_name = image.name
        if replacement.name == old_name.rsplit("/", 1)[-1]:
            image.storage.delete(old_name)
            image.storage.save(old_name, replacement)
        else:
            image.save(replacement.name, replacement, save=True)
            image.storage.delete(old_name)

        return Verdict.REWRITE, before - replacement.size
