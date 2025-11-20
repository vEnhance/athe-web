"""Management command to re-render all history entries."""

from django.core.management.base import BaseCommand

from weblog.models import HistoryEntry


class Command(BaseCommand):
    """Re-render all history entries to apply markdown extensions."""

    help = "Re-render all history entries to apply current markdown extensions"

    def handle(self, *args, **options):
        """Re-render all history entries."""
        entries = HistoryEntry.objects.all()
        count = entries.count()

        self.stdout.write(f"Re-rendering {count} history entries...")

        for entry in entries:
            # Simply saving the entry will trigger re-rendering
            entry.save()
            self.stdout.write(f"  ✓ Re-rendered: {entry.title}")

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully re-rendered {count} history entries!")
        )
