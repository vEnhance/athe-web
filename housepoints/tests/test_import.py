from datetime import timedelta

import pytest
from django.utils import timezone

from courses.models import Semester, Student
from housepoints.models import Award

# ============================================================================
# Import Housepoints Management Command Tests
# ============================================================================


@pytest.fixture
def tsv_file(tmp_path):
    """Create a temporary TSV file for testing."""

    def _create_tsv(content: str) -> str:
        tsv_path = tmp_path / "test.tsv"
        tsv_path.write_text(content)
        return str(tsv_path)

    return _create_tsv


@pytest.mark.django_db
def test_import_housepoints_basic(tsv_file):
    """Test basic import of house points from a TSV file with prefix matching."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and students
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )
    Student.objects.create(
        airtable_name="Bob Jones", semester=semester, house=Student.House.CAT
    )

    # Create TSV content with varied column names (prefix matching)
    tsv_content = "red panda\tClasses Attended\tHomework Submitted\tevent attended\tOH attended\tExtra points!\n"
    tsv_content += "Alice Smith\t3\t2\t1\t\t\n"
    tsv_content += "Bob Jones\t\t1\t\t2\t5\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    call_command("import_housepoints", tsv_path, "--semester=fa25", stdout=out)

    # Check awards were created
    # Alice: 3 class attendance (3*5=15), 2 homework (2*5=10), 1 event (1*3=3) = 3 awards
    # Bob: 1 homework (1*5=5), 2 OH (2*2=4), 5 extra points (5*2=10) = 3 awards
    assert Award.objects.count() == 6

    # Verify Alice's awards
    alice = Student.objects.get(airtable_name="Alice Smith")
    alice_awards = Award.objects.filter(student=alice)
    assert alice_awards.count() == 3
    assert (
        alice_awards.filter(award_type=Award.AwardType.CLASS_ATTENDANCE).first().points
        == 15
    )
    assert alice_awards.filter(award_type=Award.AwardType.HOMEWORK).first().points == 10
    assert alice_awards.filter(award_type=Award.AwardType.EVENT).first().points == 3

    # Verify Bob's awards
    bob = Student.objects.get(airtable_name="Bob Jones")
    bob_awards = Award.objects.filter(student=bob)
    assert bob_awards.count() == 3  # Includes staff_bonus from extra points
    assert bob_awards.filter(award_type=Award.AwardType.HOMEWORK).first().points == 5
    assert (
        bob_awards.filter(award_type=Award.AwardType.OFFICE_HOURS).first().points == 4
    )
    assert (
        bob_awards.filter(award_type=Award.AwardType.STAFF_BONUS).first().points == 10
    )  # 5 * 2


@pytest.mark.django_db
def test_import_housepoints_dry_run(tsv_file):
    """Test that dry run doesn't create any awards."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and student
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )

    # Create TSV content
    tsv_content = "Name\tClass Attendance\n"
    tsv_content += "Alice Smith\t5\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command with dry-run
    out = StringIO()
    call_command(
        "import_housepoints", tsv_path, "--semester=fa25", "--dry-run", stdout=out
    )

    # Check no awards were created
    assert Award.objects.count() == 0
    assert "DRY RUN" in out.getvalue()


@pytest.mark.django_db
def test_import_housepoints_missing_student(tsv_file):
    """Test that missing students are warned about but don't crash the import."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and one student (not the other)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )

    # Create TSV content with a missing student
    tsv_content = "Name\tClass Attendance\n"
    tsv_content += "Alice Smith\t5\n"
    tsv_content += "Missing Student\t3\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    err = StringIO()
    call_command(
        "import_housepoints", tsv_path, "--semester=fa25", stdout=out, stderr=err
    )

    # Check only Alice's award was created
    assert Award.objects.count() == 1
    assert "Missing Student" in err.getvalue()
    assert "not found" in err.getvalue()


@pytest.mark.django_db
def test_import_housepoints_student_without_house(tsv_file):
    """Test that students without houses are warned about."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and student without house
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(airtable_name="Alice Smith", semester=semester, house="")

    # Create TSV content
    tsv_content = "Name\tClass Attendance\n"
    tsv_content += "Alice Smith\t5\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    err = StringIO()
    call_command(
        "import_housepoints", tsv_path, "--semester=fa25", stdout=out, stderr=err
    )

    # Check no awards were created
    assert Award.objects.count() == 0
    assert "no house" in err.getvalue()


@pytest.mark.django_db
def test_import_housepoints_ignores_nightly_debrief(tsv_file):
    """Test that nightly debrief column is ignored."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and student
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )

    # Create TSV content with nightly debrief column
    tsv_content = "Name\tClass Attendance\tNightly Debrief\n"
    tsv_content += "Alice Smith\t5\t10\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    call_command("import_housepoints", tsv_path, "--semester=fa25", stdout=out)

    # Check only class attendance award was created (not nightly debrief)
    assert Award.objects.count() == 1
    award = Award.objects.first()
    assert award.award_type == Award.AwardType.CLASS_ATTENDANCE


@pytest.mark.django_db
def test_import_housepoints_ignores_repeated_headers(tsv_file):
    """Test that repeated column headers (same prefix) are ignored."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and students
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )

    # Create TSV content with repeated headers (like different house columns)
    # Only the first occurrence should be used (both start with "class")
    tsv_content = "Name\tClasses Attended\tClass Attendance\n"
    tsv_content += "Alice Smith\t3\t5\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    call_command("import_housepoints", tsv_path, "--semester=fa25", stdout=out)

    # Check only one class attendance award was created (from first column)
    assert Award.objects.count() == 1
    award = Award.objects.first()
    assert award.points == 15  # 3 * 5 (from first column)


@pytest.mark.django_db
def test_import_housepoints_skips_non_students(tsv_file):
    """Test that non-student rows are skipped."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and student
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )

    # Create TSV content with non-student rows
    tsv_content = "Name\tClass Attendance\n"
    tsv_content += "Alice Smith\t5\n"
    tsv_content += "non-student totals\t100\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    call_command("import_housepoints", tsv_path, "--semester=fa25", stdout=out)

    # Check only one award was created (for Alice)
    assert Award.objects.count() == 1


@pytest.mark.django_db
def test_import_housepoints_custom_description(tsv_file):
    """Test that custom description is applied to all awards."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and student
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )

    # Create TSV content
    tsv_content = "Name\tClass Attendance\n"
    tsv_content += "Alice Smith\t5\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command with custom description
    out = StringIO()
    call_command(
        "import_housepoints",
        tsv_path,
        "--semester=fa25",
        "--description=Week 1-5 import",
        stdout=out,
    )

    # Check the award has the custom description
    award = Award.objects.first()
    assert award.description == "Week 1-5 import"


@pytest.mark.django_db
def test_import_housepoints_invalid_semester(tsv_file):
    """Test that invalid semester slug causes an error."""
    from io import StringIO

    from django.core.management import call_command

    # Create TSV content
    tsv_content = "Name\tClass Attendance\n"
    tsv_content += "Alice Smith\t5\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command with invalid semester
    out = StringIO()
    err = StringIO()

    with pytest.raises(SystemExit):
        call_command(
            "import_housepoints", tsv_path, "--semester=invalid", stdout=out, stderr=err
        )


@pytest.mark.django_db
def test_import_housepoints_missing_file():
    """Test that missing file causes an error."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Run the command with non-existent file
    out = StringIO()
    err = StringIO()

    with pytest.raises(SystemExit):
        call_command(
            "import_housepoints",
            "/nonexistent/path/file.tsv",
            "--semester=fa25",
            stdout=out,
            stderr=err,
        )


@pytest.mark.django_db
def test_import_housepoints_empty_cells(tsv_file):
    """Test that empty cells are handled correctly."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and student
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )

    # Create TSV content with empty cells
    tsv_content = "Name\tClass Attendance\tHomework\tEvent Attendance\n"
    tsv_content += "Alice Smith\t\t\t3\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    call_command("import_housepoints", tsv_path, "--semester=fa25", stdout=out)

    # Check only event attendance award was created
    assert Award.objects.count() == 1
    award = Award.objects.first()
    assert award.award_type == Award.AwardType.EVENT
    assert award.points == 9  # 3 * 3


@pytest.mark.django_db
def test_import_housepoints_zero_values(tsv_file):
    """Test that zero values don't create awards."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and student
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )

    # Create TSV content with zero values
    tsv_content = "Name\tClass Attendance\tHomework\n"
    tsv_content += "Alice Smith\t0\t2\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    call_command("import_housepoints", tsv_path, "--semester=fa25", stdout=out)

    # Check only homework award was created (not class attendance with 0)
    assert Award.objects.count() == 1
    award = Award.objects.first()
    assert award.award_type == Award.AwardType.HOMEWORK


@pytest.mark.django_db
def test_import_housepoints_auto_fills_house(tsv_file):
    """Test that the house is correctly set from the student."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and students in different houses
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )
    Student.objects.create(
        airtable_name="Bob Jones", semester=semester, house=Student.House.BUNNY
    )

    # Create TSV content
    tsv_content = "Name\tClass Attendance\n"
    tsv_content += "Alice Smith\t2\n"
    tsv_content += "Bob Jones\t3\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    call_command("import_housepoints", tsv_path, "--semester=fa25", stdout=out)

    # Check house is correctly set
    alice_award = Award.objects.get(student__airtable_name="Alice Smith")
    bob_award = Award.objects.get(student__airtable_name="Bob Jones")

    assert alice_award.house == Student.House.OWL
    assert bob_award.house == Student.House.BUNNY


@pytest.mark.django_db
def test_import_housepoints_intro_true_false(tsv_file):
    """Test that intro column handles TRUE/FALSE values."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and students
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )
    Student.objects.create(
        airtable_name="Bob Jones", semester=semester, house=Student.House.CAT
    )

    # Create TSV content with intro? column using TRUE/FALSE
    tsv_content = "Name\tintro?\n"
    tsv_content += "Alice Smith\tTRUE\n"
    tsv_content += "Bob Jones\tFALSE\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    call_command("import_housepoints", tsv_path, "--semester=fa25", stdout=out)

    # Only Alice should have an intro post award (TRUE)
    assert Award.objects.count() == 1
    award = Award.objects.first()
    assert award.award_type == Award.AwardType.INTRO_POST
    assert award.student.airtable_name == "Alice Smith"
    assert award.points == 1  # 1 * 1 (intro default is 1)


@pytest.mark.django_db
def test_import_housepoints_potd_column(tsv_file):
    """Test that POTD column is correctly imported."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and student
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )

    # Create TSV content with PoTD Points column
    tsv_content = "Name\tPoTD Points\n"
    tsv_content += "Alice Smith\t3\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    call_command("import_housepoints", tsv_path, "--semester=fa25", stdout=out)

    # Check POTD award was created
    assert Award.objects.count() == 1
    award = Award.objects.first()
    assert award.award_type == Award.AwardType.POTD
    assert award.points == 30  # 3 * 10 (potd default is 10)


@pytest.mark.django_db
def test_import_housepoints_prefix_matching_variants(tsv_file):
    """Test that various column name formats are matched correctly."""
    from io import StringIO

    from django.core.management import call_command

    # Create semester and student
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(
        airtable_name="Alice Smith", semester=semester, house=Student.House.OWL
    )

    # Create TSV content with varied column names
    tsv_content = "red panda\tClasses Attended\tHomework Submitted\tevent attended\tOH attended\tPotD Points\tExtra points!\n"
    tsv_content += "Alice Smith\t1\t1\t1\t1\t1\t1\n"

    tsv_path = tsv_file(tsv_content)

    # Run the command
    out = StringIO()
    call_command("import_housepoints", tsv_path, "--semester=fa25", stdout=out)

    # Should have 6 awards (extra maps to staff_bonus with 2pt default)
    assert Award.objects.count() == 6

    # Verify award types
    award_types = set(Award.objects.values_list("award_type", flat=True))
    assert Award.AwardType.CLASS_ATTENDANCE in award_types
    assert Award.AwardType.HOMEWORK in award_types
    assert Award.AwardType.EVENT in award_types
    assert Award.AwardType.OFFICE_HOURS in award_types
    assert Award.AwardType.POTD in award_types
    assert Award.AwardType.STAFF_BONUS in award_types
