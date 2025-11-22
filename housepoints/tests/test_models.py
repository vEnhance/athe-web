from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from courses.models import Semester, Student
from housepoints.models import Award


# ============================================================================
# Model Tests
# ============================================================================


@pytest.mark.django_db
def test_student_house_assignment():
    """Test that students can be assigned to houses."""
    user = User.objects.create_user(username="testuser", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.OWL
    )

    assert student.house == "owl"
    assert student.get_house_display() == "Owls"


@pytest.mark.django_db
def test_all_house_choices():
    """Test that all five houses are available."""
    assert len(Student.House.choices) == 5
    house_codes = [choice[0] for choice in Student.House.choices]
    assert "blob" in house_codes
    assert "cat" in house_codes
    assert "owl" in house_codes
    assert "red_panda" in house_codes
    assert "bunny" in house_codes


@pytest.mark.django_db
def test_award_creation_for_student():
    """Test creating an award for a student."""
    user = User.objects.create_user(username="testuser", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.CAT
    )

    award = Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
        description="Week 1 attendance",
    )

    assert award.student == student
    assert award.house == "cat"  # Auto-filled from student
    assert award.points == 5
    assert award.award_type == "class_attendance"


@pytest.mark.django_db
def test_award_creation_for_house():
    """Test creating an award directly for a house (no student)."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    award = Award.objects.create(
        semester=semester,
        house=Student.House.BUNNY,
        award_type=Award.AwardType.HOUSE_ACTIVITY,
        points=50,
        description="Most active house in Discord",
    )

    assert award.student is None
    assert award.house == "bunny"
    assert award.points == 50


@pytest.mark.django_db
def test_award_auto_fills_house_from_student():
    """Test that house is auto-filled from student on save."""
    user = User.objects.create_user(username="testuser", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.RED_PANDA
    )

    # Create award without specifying house
    award = Award(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )
    award.save()

    assert award.house == "red_panda"


@pytest.mark.django_db
def test_award_validation_student_without_house():
    """Test that awards cannot be given to students without house assignment."""
    user = User.objects.create_user(username="testuser", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(user=user, semester=semester, house="")

    award = Award(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )

    with pytest.raises(ValidationError) as exc_info:
        award.full_clean()

    assert "without a house assignment" in str(exc_info.value)


@pytest.mark.django_db
def test_award_validation_house_mismatch():
    """Test that house mismatch between student and award is caught."""
    user = User.objects.create_user(username="testuser", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.CAT
    )

    award = Award(
        semester=semester,
        student=student,
        house=Student.House.BLOB,  # Wrong house!
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )

    with pytest.raises(ValidationError) as exc_info:
        award.full_clean()

    assert "House mismatch" in str(exc_info.value)


@pytest.mark.django_db
def test_award_validation_semester_mismatch():
    """Test that student must belong to the award's semester."""
    user = User.objects.create_user(username="testuser", password="password")
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    spring = Semester.objects.create(
        name="Spring 2026",
        slug="sp26",
        start_date=(timezone.now() + timedelta(days=120)).date(),
        end_date=(timezone.now() + timedelta(days=210)).date(),
    )
    student = Student.objects.create(user=user, semester=fall, house=Student.House.OWL)

    award = Award(
        semester=spring,  # Different semester!
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )

    with pytest.raises(ValidationError) as exc_info:
        award.full_clean()

    assert "not enrolled in" in str(exc_info.value)


@pytest.mark.django_db
def test_award_validation_house_award_requires_house():
    """Test that house-level awards must specify a house."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    award = Award(
        semester=semester,
        student=None,
        house="",  # No house specified!
        award_type=Award.AwardType.HOUSE_ACTIVITY,
        points=50,
    )

    with pytest.raises(ValidationError) as exc_info:
        award.full_clean()

    assert "must specify a house" in str(exc_info.value)


@pytest.mark.django_db
def test_semester_freeze_date():
    """Test that semester can have a freeze date for leaderboard."""
    freeze_time = timezone.now() + timedelta(days=60)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        house_points_freeze_date=freeze_time,
    )

    assert semester.house_points_freeze_date == freeze_time


@pytest.mark.django_db
def test_award_default_points():
    """Test that default points are correctly defined."""
    assert Award.DEFAULT_POINTS["intro_post"] == 1
    assert Award.DEFAULT_POINTS["class_attendance"] == 5
    assert Award.DEFAULT_POINTS["homework"] == 5
    assert Award.DEFAULT_POINTS["event"] == 3
    assert Award.DEFAULT_POINTS["office_hours"] == 2
    assert Award.DEFAULT_POINTS["potd"] == 10
    assert Award.DEFAULT_POINTS["staff_bonus"] == 2
    assert Award.DEFAULT_POINTS["house_activity"] == 50


# ============================================================================
# Award Type Tests
# ============================================================================


@pytest.mark.django_db
def test_all_award_types():
    """Test that all award types are properly defined."""
    types = [choice[0] for choice in Award.AwardType.choices]
    assert "intro_post" in types
    assert "class_attendance" in types
    assert "homework" in types
    assert "event" in types
    assert "office_hours" in types
    assert "potd" in types
    assert "staff_bonus" in types
    assert "house_activity" in types
    assert "other" in types


@pytest.mark.django_db
def test_award_str_representation_with_student():
    """Test award string representation with student."""
    user = User.objects.create_user(username="testuser", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.OWL, airtable_name="Tester"
    )
    award = Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )

    assert "Tester" in str(award)
    assert "Homework Submission" in str(award)
    assert "5 pts" in str(award)


@pytest.mark.django_db
def test_award_str_representation_house_only():
    """Test award string representation without student."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    award = Award.objects.create(
        semester=semester,
        house=Student.House.BUNNY,
        award_type=Award.AwardType.HOUSE_ACTIVITY,
        points=50,
    )

    assert "Bunnies" in str(award)
    assert "House Activity Bonus" in str(award)
    assert "50 pts" in str(award)


# ============================================================================
# Introduction Post Award Constraint Tests
# ============================================================================


@pytest.mark.django_db
def test_intro_post_awarded_only_once_per_student():
    """Test that Introduction Post can only be awarded once per student per semester."""
    user = User.objects.create_user(username="testuser", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.OWL, airtable_name="Tester"
    )

    # First intro post award should succeed
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.INTRO_POST,
        points=1,
        description="First intro post",
    )

    # Second intro post award should fail due to unique constraint
    with pytest.raises(ValidationError) as exc_info:
        Award.objects.create(
            semester=semester,
            student=student,
            award_type=Award.AwardType.INTRO_POST,
            points=1,
            description="Duplicate intro post",
        )

    assert "unique_intro_post_per_student" in str(exc_info.value)


@pytest.mark.django_db
def test_intro_post_can_be_awarded_in_different_semesters():
    """Test that the same student can receive Introduction Post in different semesters."""
    user = User.objects.create_user(username="testuser", password="password")
    fall = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    spring = Semester.objects.create(
        name="Spring 2026",
        slug="sp26",
        start_date=(timezone.now() + timedelta(days=120)).date(),
        end_date=(timezone.now() + timedelta(days=210)).date(),
    )

    # Create student enrollments in both semesters
    student_fall = Student.objects.create(
        user=user, semester=fall, house=Student.House.CAT, airtable_name="Tester"
    )
    student_spring = Student.objects.create(
        user=user, semester=spring, house=Student.House.CAT, airtable_name="Tester"
    )

    # Should be able to award intro post in both semesters
    award_fall = Award.objects.create(
        semester=fall,
        student=student_fall,
        award_type=Award.AwardType.INTRO_POST,
        points=1,
    )
    award_spring = Award.objects.create(
        semester=spring,
        student=student_spring,
        award_type=Award.AwardType.INTRO_POST,
        points=1,
    )

    assert award_fall.id is not None
    assert award_spring.id is not None
    assert Award.objects.filter(award_type=Award.AwardType.INTRO_POST).count() == 2


@pytest.mark.django_db
def test_other_award_types_can_be_awarded_multiple_times():
    """Test that award types other than Introduction Post can be awarded multiple times."""
    user = User.objects.create_user(username="testuser", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.BLOB, airtable_name="Tester"
    )

    # Create multiple homework awards - should all succeed
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
        description="Homework 1",
    )
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
        description="Homework 2",
    )
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
        description="Homework 3",
    )

    assert Award.objects.filter(award_type=Award.AwardType.HOMEWORK).count() == 3


@pytest.mark.django_db
def test_class_attendance_can_be_awarded_multiple_times():
    """Test that class attendance can be awarded multiple times to the same student."""
    user = User.objects.create_user(username="testuser", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user,
        semester=semester,
        house=Student.House.RED_PANDA,
        airtable_name="Tester",
    )

    # Create multiple class attendance awards
    for i in range(5):
        Award.objects.create(
            semester=semester,
            student=student,
            award_type=Award.AwardType.CLASS_ATTENDANCE,
            points=5,
            description=f"Week {i + 1} attendance",
        )

    assert (
        Award.objects.filter(award_type=Award.AwardType.CLASS_ATTENDANCE).count() == 5
    )


@pytest.mark.django_db
def test_intro_post_constraint_only_applies_to_student_awards():
    """Test that intro post constraint only applies when student is set (not house-level)."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # House-level intro post awards should not be constrained
    # (though this is unlikely in practice)
    Award.objects.create(
        semester=semester,
        house=Student.House.OWL,
        award_type=Award.AwardType.INTRO_POST,
        points=1,
        description="House intro post 1",
    )
    Award.objects.create(
        semester=semester,
        house=Student.House.OWL,
        award_type=Award.AwardType.INTRO_POST,
        points=1,
        description="House intro post 2",
    )

    # Should have 2 awards (constraint doesn't apply to house-level awards)
    assert Award.objects.filter(award_type=Award.AwardType.INTRO_POST).count() == 2
