"""
Management command to bulk import house points from a TSV file.

The TSV format should have:
- First column: student name (airtable_name) - header name is ignored
- Subsequent columns: award counts for different categories

Categories are matched by prefix (case-insensitive):
- starts with "class" -> class_attendance
- starts with "homework" -> homework
- starts with "event" -> event
- starts with "oh" -> office_hours
- starts with "intro" -> intro_post (TRUE/FALSE values supported)
- starts with "potd" -> potd
- starts with "extra" -> other
- starts with "nightly" -> ignored

For non-empty cells, we create a single Award object with points = count * default_points.
For intro columns, TRUE/FALSE are converted to 1/0.
"""

import csv
import sys
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Semester, Student
from housepoints.models import Award


# Prefix mappings for column headers (checked in order)
PREFIX_MAP: list[tuple[str, str | None]] = [
    ("class", Award.AwardType.CLASS_ATTENDANCE),
    ("homework", Award.AwardType.HOMEWORK),
    ("event", Award.AwardType.EVENT),
    ("oh", Award.AwardType.OFFICE_HOURS),
    ("intro", Award.AwardType.INTRO_POST),
    ("potd", Award.AwardType.POTD),
    ("extra", Award.AwardType.STAFF_BONUS),
    ("nightly", None),  # Ignored
]


def get_award_type_for_header(header: str) -> str | None:
    """
    Determine the award type for a column header using prefix matching.

    Returns the award type string, or None if the column should be ignored.
    """
    header_lower = header.strip().lower()
    if not header_lower:
        return None

    for prefix, award_type in PREFIX_MAP:
        if header_lower.startswith(prefix):
            return award_type

    return None


def parse_header(header_row: list[str]) -> list[tuple[int, str] | None]:
    """
    Parse the header row and return a list mapping column index to award type.

    Returns a list where each element is either:
    - A tuple (col_index, award_type) for valid category columns
    - None for columns to skip (name column, ignored categories, unknown)

    Column headers may be repeated for each house; we only use the first occurrence.
    The first column is always treated as the name column regardless of header.
    """
    seen_award_types: set[str] = set()
    column_mapping: list[tuple[int, str] | None] = []

    for i, header in enumerate(header_row):
        if i == 0:
            # First column is always the name (header is ignored)
            column_mapping.append(None)
            continue

        award_type = get_award_type_for_header(header)

        if award_type is None:
            column_mapping.append(None)
            continue

        # Only use first occurrence of each award type
        if award_type not in seen_award_types:
            seen_award_types.add(award_type)
            column_mapping.append((i, award_type))
        else:
            column_mapping.append(None)

    return column_mapping


def parse_cell_value(value: str, is_intro: bool = False) -> int | None:
    """
    Parse a cell value as an integer count.

    For intro columns, TRUE/FALSE are converted to 1/0.
    Returns None for empty/non-numeric values or zero.
    """
    value = value.strip().upper()
    if not value:
        return None

    # Handle TRUE/FALSE for intro columns
    if is_intro:
        if value == "TRUE":
            return 1
        elif value == "FALSE":
            return None  # FALSE means no intro post

    try:
        count = int(value)
        return count if count > 0 else None
    except ValueError:
        return None


class Command(BaseCommand):
    help = "Bulk import house points from a TSV file"

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument(
            "tsv_file",
            type=str,
            help="Path to the TSV file to import",
        )
        parser.add_argument(
            "--semester",
            type=str,
            required=True,
            help="Semester slug to import awards into",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be imported without actually creating records",
        )
        parser.add_argument(
            "--description",
            type=str,
            default="Bulk imported from spreadsheet",
            help="Description to add to all awards (default: 'Bulk imported from spreadsheet')",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        tsv_file = options["tsv_file"]
        semester_slug = options["semester"]
        dry_run = options["dry_run"]
        description = options["description"]

        # Get the semester
        try:
            semester = Semester.objects.get(slug=semester_slug)
        except Semester.DoesNotExist:
            self.stderr.write(
                self.style.ERROR(f"Semester with slug '{semester_slug}' not found")
            )
            sys.exit(1)

        self.stdout.write(f"Importing house points for semester: {semester}")
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN - no records will be created")
            )

        # Read and parse the TSV file
        try:
            with open(tsv_file, newline="", encoding="utf-8") as f:
                reader = csv.reader(f, delimiter="\t")
                rows = list(reader)
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {tsv_file}"))
            sys.exit(1)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error reading file: {e}"))
            sys.exit(1)

        if len(rows) < 2:
            self.stderr.write(self.style.ERROR("TSV file must have at least 2 rows"))
            sys.exit(1)

        # Parse header
        header_row = rows[0]
        column_mapping = parse_header(header_row)

        # Find which columns have valid categories
        valid_columns = [(i, m) for i, m in enumerate(column_mapping) if m is not None]
        if not valid_columns:
            self.stderr.write(self.style.ERROR("No valid category columns found"))
            sys.exit(1)

        self.stdout.write(f"Found {len(valid_columns)} category columns to import")

        # Prefetch all students for this semester
        students_by_name = {
            s.airtable_name: s for s in Student.objects.filter(semester=semester)
        }

        awards_to_create: list[Award] = []
        warnings: list[str] = []
        skipped_rows = 0
        processed_students = 0

        for row_num, row in enumerate(rows[1:], start=2):
            if not row:
                continue

            # Get student name from first column
            student_name = row[0].strip()
            if not student_name:
                continue

            # Skip non-student rows (they should be empty anyway)
            if "non-student" in student_name.lower():
                skipped_rows += 1
                continue

            # Look up student
            student = students_by_name.get(student_name)
            if student is None:
                warnings.append(
                    f"Row {row_num}: Student '{student_name}' not found, skipping"
                )
                continue

            if not student.house:
                warnings.append(
                    f"Row {row_num}: Student '{student_name}' has no house, skipping"
                )
                continue

            processed_students += 1
            student_awards = 0

            # Process each valid column
            for col_idx, (_, award_type) in valid_columns:
                # Get cell value
                if col_idx >= len(row):
                    continue

                is_intro = award_type == Award.AwardType.INTRO_POST.value
                count = parse_cell_value(row[col_idx], is_intro=is_intro)
                if count is None:
                    continue

                # Calculate total points
                default_points = Award.DEFAULT_POINTS.get(award_type, 0)
                total_points = count * default_points

                if total_points <= 0:
                    continue

                # Create award object (don't save yet)
                award = Award(
                    semester=semester,
                    student=student,
                    house=student.house,
                    award_type=award_type,
                    points=total_points,
                    description=description,
                )
                awards_to_create.append(award)
                student_awards += 1

            if student_awards > 0 and not dry_run:
                self.stdout.write(
                    f"  {student_name}: {student_awards} award(s) prepared"
                )

        # Print warnings
        for warning in warnings:
            self.stderr.write(self.style.WARNING(warning))

        self.stdout.write(f"\nProcessed {processed_students} students")
        self.stdout.write(f"Skipped {skipped_rows} non-student rows")
        self.stdout.write(f"Total awards to create: {len(awards_to_create)}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\nDry run complete"))
            # Show summary by award type
            type_counts: dict[str, int] = {}
            type_points: dict[str, int] = {}
            for award in awards_to_create:
                type_counts[award.award_type] = type_counts.get(award.award_type, 0) + 1
                type_points[award.award_type] = (
                    type_points.get(award.award_type, 0) + award.points
                )

            self.stdout.write("\nSummary by award type:")
            for award_type, count in sorted(type_counts.items()):
                points = type_points[award_type]
                self.stdout.write(f"  {award_type}: {count} awards, {points} total pts")
            return

        # Actually create the awards
        if not awards_to_create:
            self.stdout.write(self.style.WARNING("No awards to create"))
            return

        with transaction.atomic():
            # Use bulk_create for efficiency, but skip validation since we built
            # the objects carefully
            Award.objects.bulk_create(awards_to_create)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully created {len(awards_to_create)} awards!"
            )
        )

        # Show summary by award type
        type_counts = {}
        type_points = {}
        for award in awards_to_create:
            type_counts[award.award_type] = type_counts.get(award.award_type, 0) + 1
            type_points[award.award_type] = (
                type_points.get(award.award_type, 0) + award.points
            )

        self.stdout.write("\nSummary by award type:")
        for award_type, count in sorted(type_counts.items()):
            points = type_points[award_type]
            self.stdout.write(f"  {award_type}: {count} awards, {points} total pts")
