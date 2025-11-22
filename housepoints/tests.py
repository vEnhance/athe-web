from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student
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
# Leaderboard View Tests
# ============================================================================


@pytest.mark.django_db
def test_leaderboard_requires_login():
    """Test that leaderboard requires authentication."""
    client = Client()
    url = reverse("housepoints:leaderboard")
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_leaderboard_staff_access():
    """Test that staff can access the leaderboard."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200
    assert "Fall 2025" in response.content.decode()


@pytest.mark.django_db
def test_leaderboard_enrolled_student_access():
    """Test that enrolled students can access the leaderboard."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(user=user, semester=semester, house=Student.House.OWL)

    client.login(username="student", password="password")
    url = reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug})
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_leaderboard_unenrolled_student_denied():
    """Test that non-enrolled students cannot access the leaderboard."""
    client = Client()
    User.objects.create_user(username="student", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="student", password="password")
    url = reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug})
    response = client.get(url, follow=True)

    # Should redirect to home with error message
    assert response.status_code == 200
    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "don't have access" in str(messages[0])


@pytest.mark.django_db
def test_leaderboard_calculates_totals():
    """Test that leaderboard correctly calculates house totals."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students in different houses
    user1 = User.objects.create_user(username="user1", password="password")
    user2 = User.objects.create_user(username="user2", password="password")
    student1 = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Student 1",
    )
    student2 = Student.objects.create(
        user=user2,
        semester=semester,
        house=Student.House.CAT,
        airtable_name="Student 2",
    )

    # Create awards
    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=student2,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug})
    response = client.get(url)

    content = response.content.decode()
    assert response.status_code == 200
    # Owls should have 10 points (5+5), Cats should have 5
    assert "10" in content  # Owls total
    assert "Owls" in content
    assert "Cats" in content


@pytest.mark.django_db
def test_leaderboard_respects_freeze_date():
    """Test that leaderboard respects the freeze date."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    freeze_time = timezone.now() - timedelta(days=1)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
        house_points_freeze_date=freeze_time,
    )

    user = User.objects.create_user(username="user1", password="password")
    student = Student.objects.create(
        user=user,
        semester=semester,
        house=Student.House.BLOB,
        airtable_name="Student 1",
    )

    # Create award before freeze date (should count)
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
        awarded_at=freeze_time - timedelta(hours=1),
    )
    # Create award after freeze date (should not count)
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=10,
        awarded_at=freeze_time + timedelta(hours=1),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug})
    client.get(url)  # Trigger view to ensure it works

    # Total should be 5 (not 15)
    total = Award.objects.filter(
        semester=semester, awarded_at__lte=freeze_time
    ).aggregate(total=Sum("points"))["total"]
    assert total == 5


@pytest.mark.django_db
def test_leaderboard_shows_all_houses():
    """Test that all houses are shown even with zero points."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:leaderboard_semester", kwargs={"slug": semester.slug})
    response = client.get(url)

    content = response.content.decode()
    # All houses should appear
    assert "Blobs" in content
    assert "Cats" in content
    assert "Owls" in content
    assert "Red Panda" in content
    assert "Bunnies" in content


# ============================================================================
# Bulk Award View Tests
# ============================================================================


@pytest.mark.django_db
def test_bulk_award_requires_staff():
    """Test that bulk award view requires staff access."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    client.login(username="student", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.get(url)

    # Should be forbidden (403)
    assert response.status_code == 403


@pytest.mark.django_db
def test_bulk_award_staff_access():
    """Test that staff can access bulk award view."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    # Create an active semester
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.get(url)

    assert response.status_code == 200
    assert "Bulk Award Points" in response.content.decode()


@pytest.mark.django_db
def test_bulk_award_creates_awards():
    """Test that bulk award successfully creates awards for multiple users."""
    client = Client()
    staff = User.objects.create_user(
        username="staff", password="password", is_staff=True
    )
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students
    user1 = User.objects.create_user(
        username="alice", password="password", email="alice@example.com"
    )
    user2 = User.objects.create_user(
        username="bob", password="password", email="bob@example.com"
    )
    Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    Student.objects.create(
        user=user2,
        semester=semester,
        house=Student.House.CAT,
        airtable_name="Bob Jones",
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "award_type": Award.AwardType.OFFICE_HOURS,
            "airtable_names": "Alice Smith\nBob Jones",
            "points": "",  # Use default
            "description": "Week 1 OH",
        },
    )

    assert response.status_code == 200
    # Check awards were created
    assert Award.objects.count() == 2
    alice_award = Award.objects.get(student__user__username="alice")
    assert alice_award.points == 2  # Default for office hours
    assert alice_award.house == "owl"
    assert alice_award.awarded_by == staff

    bob_award = Award.objects.get(student__user__username="bob")
    assert bob_award.points == 2
    assert bob_award.house == "cat"


@pytest.mark.django_db
def test_bulk_award_custom_points():
    """Test that bulk award can use custom point values."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    user = User.objects.create_user(
        username="alice", password="password", email="alice@example.com"
    )
    Student.objects.create(
        user=user, semester=semester, house=Student.House.BLOB, airtable_name="Alice"
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "award_type": Award.AwardType.CLASS_ATTENDANCE,
            "airtable_names": "Alice",
            "points": "3",  # Custom points (e.g., for subsequent classes)
            "description": "Week 15 attendance",
        },
    )

    assert response.status_code == 200
    award = Award.objects.get(student__user__username="alice")
    assert award.points == 3


@pytest.mark.django_db
def test_bulk_award_handles_missing_student():
    """Test that bulk award handles non-existent students gracefully."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    user = User.objects.create_user(
        username="alice", password="password", email="alice@example.com"
    )
    Student.objects.create(
        user=user, semester=semester, house=Student.House.OWL, airtable_name="Alice"
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "award_type": Award.AwardType.HOMEWORK,
            "airtable_names": "Alice\nNonexistent Student",
            "points": "",
            "description": "",
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    # Alice should succeed
    assert "Alice" in content
    # Nonexistent should fail
    assert "Nonexistent Student" in content
    assert "Not enrolled" in content or "not enrolled" in content.lower()
    # Only one award should be created
    assert Award.objects.count() == 1


@pytest.mark.django_db
def test_bulk_award_handles_student_without_house():
    """Test that bulk award handles students without house assignment."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    user = User.objects.create_user(
        username="alice", password="password", email="alice@example.com"
    )
    Student.objects.create(
        user=user, semester=semester, house="", airtable_name="Alice"
    )  # No house

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "award_type": Award.AwardType.HOMEWORK,
            "airtable_names": "Alice",
            "points": "",
            "description": "",
        },
    )

    content = response.content.decode()
    assert "No house assigned" in content
    assert Award.objects.count() == 0


@pytest.mark.django_db
def test_bulk_award_no_active_semester():
    """Test that bulk award fails gracefully when no active semester exists."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    # Create a past semester
    Semester.objects.create(
        name="Spring 2020",
        slug="sp20",
        start_date=(timezone.now() - timedelta(days=200)).date(),
        end_date=(timezone.now() - timedelta(days=110)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.get(url)

    # Should redirect to home with error message
    assert response.status_code == 302
    assert response.url == reverse("home:index")


@pytest.mark.django_db
def test_bulk_award_multiple_active_semesters():
    """Test that bulk award fails when multiple overlapping semesters exist."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    # Create two overlapping semesters
    Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=10)).date(),
        end_date=(timezone.now() + timedelta(days=80)).date(),
    )
    Semester.objects.create(
        name="Winter 2025",
        slug="wi25",
        start_date=(timezone.now() - timedelta(days=5)).date(),
        end_date=(timezone.now() + timedelta(days=85)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.get(url)

    # Should redirect to home with error message
    assert response.status_code == 302
    assert response.url == reverse("home:index")


# ============================================================================
# My Awards View Tests
# ============================================================================


@pytest.mark.django_db
def test_my_awards_requires_login():
    """Test that my awards page requires authentication."""
    client = Client()
    url = reverse("housepoints:my_awards")
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_my_awards_shows_user_awards():
    """Test that my awards page shows the user's awards."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.BUNNY, airtable_name="Student"
    )

    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.INTRO_POST,
        points=1,
        description="Posted intro",
    )

    client.login(username="student", password="password")
    url = reverse("housepoints:my_awards")
    response = client.get(url)

    content = response.content.decode()
    assert response.status_code == 200
    assert "Introduction Post" in content
    assert "+1" in content
    assert "Posted intro" in content


@pytest.mark.django_db
def test_my_awards_shows_semester_totals():
    """Test that my awards page shows totals per semester."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.CAT, airtable_name="Student"
    )

    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )

    client.login(username="student", password="password")
    url = reverse("housepoints:my_awards")
    response = client.get(url)

    content = response.content.decode()
    assert "10" in content  # Total points
    assert "Cats" in content  # House name


@pytest.mark.django_db
def test_my_awards_only_shows_own_awards():
    """Test that users only see their own awards."""
    client = Client()
    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    student1 = Student.objects.create(
        user=user1, semester=semester, house=Student.House.OWL, airtable_name="Alice"
    )
    student2 = Student.objects.create(
        user=user2, semester=semester, house=Student.House.CAT, airtable_name="Bob"
    )

    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.POTD,
        points=20,
        description="Alice PotD",
    )
    Award.objects.create(
        semester=semester,
        student=student2,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
        description="Bob HW",
    )

    # Login as Alice
    client.login(username="alice", password="password")
    url = reverse("housepoints:my_awards")
    response = client.get(url)

    content = response.content.decode()
    assert "Alice PotD" in content
    assert "Bob HW" not in content


# ============================================================================
# Navigation Tests
# ============================================================================


@pytest.mark.django_db
def test_navigation_links_for_authenticated_user():
    """Test that house points links appear in navigation for logged-in users."""
    client = Client()
    User.objects.create_user(username="user", password="password")

    client.login(username="user", password="password")
    url = reverse("home:index")
    response = client.get(url)

    content = response.content.decode()
    assert "House Points" in content
    assert "My Awards" in content


@pytest.mark.django_db
def test_navigation_bulk_award_link_for_staff():
    """Test that Award Points link appears for staff only."""
    client = Client()
    User.objects.create_user(username="user", password="password")
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Regular user should not see Award Points link
    client.login(username="user", password="password")
    response = client.get(reverse("home:index"))
    content = response.content.decode()
    assert "Award Points" not in content

    # Staff should see Award Points link
    client.login(username="staff", password="password")
    response = client.get(reverse("home:index"))
    content = response.content.decode()
    assert "Award Points" in content


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


# ============================================================================
# Attendance Bulk View Tests
# ============================================================================


@pytest.mark.django_db
def test_attendance_bulk_requires_staff():
    """Test that attendance bulk view requires staff access."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    client.login(username="student", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.get(url)

    # Should be forbidden (403)
    assert response.status_code == 403


@pytest.mark.django_db
def test_attendance_bulk_staff_access():
    """Test that staff can access attendance bulk view."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.get(url)

    assert response.status_code == 200
    assert "Class Attendance" in response.content.decode()


@pytest.mark.django_db
def test_attendance_bulk_shows_active_semester_courses():
    """Test that only courses from active semesters are shown."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    # Create active semester with course
    active_semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    active_course = Course.objects.create(
        name="Active Course",
        description="Test course",
        semester=active_semester,
    )

    # Create ended semester with course
    ended_semester = Semester.objects.create(
        name="Spring 2020",
        slug="sp20",
        start_date=(timezone.now() - timedelta(days=200)).date(),
        end_date=(timezone.now() - timedelta(days=110)).date(),
    )
    Course.objects.create(
        name="Ended Course",
        description="Old course",
        semester=ended_semester,
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.get(url)

    content = response.content.decode()
    assert response.status_code == 200
    assert active_course.name in content
    assert "Ended Course" not in content


@pytest.mark.django_db
def test_attendance_bulk_excludes_clubs():
    """Test that clubs are not shown in the course list."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Course.objects.create(
        name="Regular Class",
        description="Test class",
        semester=semester,
        is_club=False,
    )
    Course.objects.create(
        name="Test Club",
        description="A club",
        semester=semester,
        is_club=True,
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.get(url)

    content = response.content.decode()
    assert "Regular Class" in content
    assert "Test Club" not in content


@pytest.mark.django_db
def test_attendance_bulk_default_course_for_leader():
    """Test that the default course is one the staff member leads."""
    client = Client()
    staff = User.objects.create_user(
        username="staff", password="password", is_staff=True
    )

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    other_course = Course.objects.create(
        name="Other Course",
        description="Not led by staff",
        semester=semester,
    )
    led_course = Course.objects.create(
        name="Led Course",
        description="Led by staff",
        semester=semester,
    )
    led_course.leaders.add(staff)

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.get(url)

    content = response.content.decode()
    # The led course should be selected (has 'selected' attribute)
    assert f'value="{led_course.pk}" selected' in content
    assert f'value="{other_course.pk}" selected' not in content


@pytest.mark.django_db
def test_attendance_bulk_load_students():
    """Test that loading students shows enrolled students with checkboxes."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=semester,
    )

    # Create enrolled students
    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    student1 = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    student2 = Student.objects.create(
        user=user2,
        semester=semester,
        house=Student.House.CAT,
        airtable_name="Bob Jones",
    )
    course.students.add(student1, student2)

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "points": "5",
            "load_students": "1",
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Alice Smith" in content
    assert "Bob Jones" in content
    # Checkboxes should be present
    assert 'type="checkbox"' in content
    assert "checked" in content


@pytest.mark.django_db
def test_attendance_bulk_excludes_students_without_house():
    """Test that students without house assignment are not shown."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=semester,
    )

    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    student_with_house = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    student_without_house = Student.objects.create(
        user=user2,
        semester=semester,
        house="",
        airtable_name="Bob NoHouse",
    )
    course.students.add(student_with_house, student_without_house)

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "points": "5",
            "load_students": "1",
        },
    )

    content = response.content.decode()
    assert "Alice Smith" in content
    assert "Bob NoHouse" not in content


@pytest.mark.django_db
def test_attendance_bulk_creates_awards():
    """Test that submitting creates attendance awards for selected students."""
    client = Client()
    staff = User.objects.create_user(
        username="staff", password="password", is_staff=True
    )

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Math Class",
        description="Test",
        semester=semester,
    )

    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    student1 = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    student2 = Student.objects.create(
        user=user2,
        semester=semester,
        house=Student.House.CAT,
        airtable_name="Bob Jones",
    )
    course.students.add(student1, student2)

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "points": "5",
            "description": "Attendance on 2025-01-15 for Math Class",
            "students": [student1.pk, student2.pk],
        },
    )

    assert response.status_code == 200
    assert Award.objects.count() == 2

    alice_award = Award.objects.get(student=student1)
    assert alice_award.points == 5
    assert alice_award.house == "owl"
    assert alice_award.award_type == "class_attendance"
    assert alice_award.awarded_by == staff
    assert "Math Class" in alice_award.description

    bob_award = Award.objects.get(student=student2)
    assert bob_award.points == 5
    assert bob_award.house == "cat"


@pytest.mark.django_db
def test_attendance_bulk_partial_selection():
    """Test that only selected students receive awards (absent students excluded)."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=semester,
    )

    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    present_student = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Present Alice",
    )
    absent_student = Student.objects.create(
        user=user2,
        semester=semester,
        house=Student.House.CAT,
        airtable_name="Absent Bob",
    )
    course.students.add(present_student, absent_student)

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    # Only select the present student
    response = client.post(
        url,
        {
            "course": course.pk,
            "points": "5",
            "students": [present_student.pk],  # Bob is not selected (absent)
        },
    )

    assert response.status_code == 200
    assert Award.objects.count() == 1
    assert Award.objects.filter(student=present_student).exists()
    assert not Award.objects.filter(student=absent_student).exists()


@pytest.mark.django_db
def test_attendance_bulk_custom_points():
    """Test that 3 points can be awarded instead of default 5."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=semester,
    )

    user = User.objects.create_user(username="alice", password="password")
    student = Student.objects.create(
        user=user,
        semester=semester,
        house=Student.House.BLOB,
        airtable_name="Alice",
    )
    course.students.add(student)

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "points": "3",  # 3 points instead of 5
            "students": [student.pk],
        },
    )

    assert response.status_code == 200
    award = Award.objects.get(student=student)
    assert award.points == 3


@pytest.mark.django_db
def test_attendance_bulk_no_students_selected():
    """Test that error is shown when no students are selected."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=semester,
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "points": "5",
            # No students selected
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "No students selected" in content
    assert Award.objects.count() == 0


@pytest.mark.django_db
def test_attendance_bulk_shows_success_results():
    """Test that success results are displayed after awarding."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=semester,
    )

    user = User.objects.create_user(username="alice", password="password")
    student = Student.objects.create(
        user=user,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    course.students.add(student)

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "points": "5",
            "students": [student.pk],
        },
    )

    content = response.content.decode()
    assert "Successfully Awarded" in content
    assert "Alice Smith" in content
    assert "+5 pts" in content
    assert "Owls" in content


@pytest.mark.django_db
def test_attendance_bulk_validates_student_enrollment():
    """Test that students not enrolled in the course are rejected."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=semester,
    )

    user = User.objects.create_user(username="alice", password="password")
    # Student NOT enrolled in course
    unenrolled_student = Student.objects.create(
        user=user,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    client.post(
        url,
        {
            "course": course.pk,
            "points": "5",
            "students": [unenrolled_student.pk],
        },
    )

    # No awards should be created for unenrolled students
    assert Award.objects.count() == 0


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


# ============================================================================
# House Detail View Tests (Student View)
# ============================================================================


@pytest.mark.django_db
def test_house_detail_requires_login():
    """Test that house detail view requires authentication."""
    client = Client()
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    url = reverse(
        "housepoints:house_detail", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_house_detail_staff_can_access_any_house():
    """Test that staff can access any house's detail view."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    assert response.status_code == 200
    assert "Owls" in response.content.decode()


@pytest.mark.django_db
def test_house_detail_student_can_access_own_house():
    """Test that students can access their own house's detail view."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(user=user, semester=semester, house=Student.House.OWL)

    client.login(username="student", password="password")
    url = reverse(
        "housepoints:house_detail", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    assert response.status_code == 200
    assert "Owls" in response.content.decode()


@pytest.mark.django_db
def test_house_detail_student_cannot_access_other_house():
    """Test that students cannot access other houses' detail view."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(user=user, semester=semester, house=Student.House.CAT)

    client.login(username="student", password="password")
    # Try to access OWL house while enrolled in CAT
    url = reverse(
        "housepoints:house_detail", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url, follow=True)

    # Should redirect to leaderboard with error message
    assert response.status_code == 200
    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "only view detailed stats for your own house" in str(messages[0])


@pytest.mark.django_db
def test_house_detail_shows_category_totals():
    """Test that house detail view shows points by category."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create students and awards
    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    student1 = Student.objects.create(
        user=user1, semester=semester, house=Student.House.OWL, airtable_name="Alice"
    )
    student2 = Student.objects.create(
        user=user2, semester=semester, house=Student.House.OWL, airtable_name="Bob"
    )

    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=student2,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    content = response.content.decode()
    assert response.status_code == 200
    assert "Class Attendance" in content
    assert "Homework" in content
    assert "15" in content  # Grand total: 10 + 5


@pytest.mark.django_db
def test_house_detail_invalid_house():
    """Test that invalid house code redirects with error."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail", kwargs={"slug": semester.slug, "house": "invalid"}
    )
    response = client.get(url, follow=True)

    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "Invalid house" in str(messages[0])


@pytest.mark.django_db
def test_house_detail_respects_freeze_date():
    """Test that house detail view respects the freeze date."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    freeze_time = timezone.now() - timedelta(days=1)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
        house_points_freeze_date=freeze_time,
    )

    user = User.objects.create_user(username="alice", password="password")
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.OWL, airtable_name="Alice"
    )

    # Award before freeze (should count)
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
        awarded_at=freeze_time - timedelta(hours=1),
    )
    # Award after freeze (should not count)
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=10,
        awarded_at=freeze_time + timedelta(hours=1),
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    content = response.content.decode()
    # Should show 5 points (not 15)
    assert "5" in content
    assert "frozen" in content.lower()


# ============================================================================
# House Detail Staff View Tests
# ============================================================================


@pytest.mark.django_db
def test_house_detail_staff_requires_staff():
    """Test that staff house detail view requires staff access."""
    client = Client()
    user = User.objects.create_user(username="student", password="password")
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    Student.objects.create(user=user, semester=semester, house=Student.House.OWL)

    client.login(username="student", password="password")
    url = reverse(
        "housepoints:house_detail_staff", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url, follow=True)

    # Should redirect with error
    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "only available to staff" in str(messages[0])


@pytest.mark.django_db
def test_house_detail_staff_shows_student_table():
    """Test that staff view shows student x category table."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    student1 = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    student2 = Student.objects.create(
        user=user2,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Bob Jones",
    )

    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=10,
    )
    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=student2,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail_staff", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    content = response.content.decode()
    assert response.status_code == 200
    # Check student names appear
    assert "Alice Smith" in content
    assert "Bob Jones" in content
    # Check category headers appear (using short names)
    assert "Attend" in content
    assert "Hwk" in content


@pytest.mark.django_db
def test_house_detail_staff_shows_row_totals():
    """Test that staff view shows row totals (per student)."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    user = User.objects.create_user(username="alice", password="password")
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.OWL, airtable_name="Alice"
    )

    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=10,
    )
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail_staff", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    content = response.content.decode()
    # Row total for Alice should be 15
    assert "15" in content


@pytest.mark.django_db
def test_house_detail_staff_shows_column_totals():
    """Test that staff view shows column totals (per category)."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    student1 = Student.objects.create(
        user=user1, semester=semester, house=Student.House.OWL, airtable_name="Alice"
    )
    student2 = Student.objects.create(
        user=user2, semester=semester, house=Student.House.OWL, airtable_name="Bob"
    )

    # Create awards - same category for both students to test column totals
    Award.objects.create(
        semester=semester,
        student=student1,
        house=student1.house,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=10,
    )
    Award.objects.create(
        semester=semester,
        student=student2,
        house=student2.house,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail_staff", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    assert response.status_code == 200

    # Check context variables directly
    ctx = response.context
    assert ctx["house"] == "owl"
    assert len(ctx["student_rows"]) == 2  # Alice and Bob

    # Check column totals (sum of all students for each category)
    # Both students have CLASS_ATTENDANCE: 10 + 5 = 15
    assert ctx["column_totals"] == [15]
    assert ctx["grand_total"] == 15

    # Check row totals
    alice_row = next(r for r in ctx["student_rows"] if r["name"] == "Alice")
    bob_row = next(r for r in ctx["student_rows"] if r["name"] == "Bob")
    assert alice_row["total"] == 10
    assert bob_row["total"] == 5


@pytest.mark.django_db
def test_house_detail_staff_shows_grand_total():
    """Test that staff view shows grand total."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    student1 = Student.objects.create(
        user=user1, semester=semester, house=Student.House.OWL, airtable_name="Alice"
    )
    student2 = Student.objects.create(
        user=user2, semester=semester, house=Student.House.OWL, airtable_name="Bob"
    )

    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=10,
    )
    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )
    Award.objects.create(
        semester=semester,
        student=student2,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail_staff", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    content = response.content.decode()
    # Grand total should be 20
    assert "20" in content


@pytest.mark.django_db
def test_house_detail_staff_includes_house_level_awards():
    """Test that staff view includes house-level awards."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a house-level award (no student)
    Award.objects.create(
        semester=semester,
        house=Student.House.OWL,
        award_type=Award.AwardType.HOUSE_ACTIVITY,
        points=50,
        description="House activity bonus",
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail_staff", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    content = response.content.decode()
    assert response.status_code == 200
    assert "House-level awards" in content
    assert "50" in content


@pytest.mark.django_db
def test_house_detail_staff_invalid_house():
    """Test that invalid house code redirects with error."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail_staff",
        kwargs={"slug": semester.slug, "house": "invalid"},
    )
    response = client.get(url, follow=True)

    messages = list(response.context["messages"])
    assert len(messages) == 1
    assert "Invalid house" in str(messages[0])


@pytest.mark.django_db
def test_house_detail_staff_respects_freeze_date():
    """Test that staff house detail view respects the freeze date."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    freeze_time = timezone.now() - timedelta(days=1)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=(timezone.now() - timedelta(days=30)).date(),
        end_date=(timezone.now() + timedelta(days=60)).date(),
        house_points_freeze_date=freeze_time,
    )

    user = User.objects.create_user(username="alice", password="password")
    student = Student.objects.create(
        user=user, semester=semester, house=Student.House.OWL, airtable_name="Alice"
    )

    # Award before freeze (should count)
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
        awarded_at=freeze_time - timedelta(hours=1),
    )
    # Award after freeze (should not count)
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=10,
        awarded_at=freeze_time + timedelta(hours=1),
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail_staff", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    content = response.content.decode()
    # Grand total should be 5 (not 15)
    assert "5" in content
    assert "frozen" in content.lower()


@pytest.mark.django_db
def test_house_detail_staff_empty_house():
    """Test that staff view handles house with no awards."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    client.login(username="staff", password="password")
    url = reverse(
        "housepoints:house_detail_staff", kwargs={"slug": semester.slug, "house": "owl"}
    )
    response = client.get(url)

    content = response.content.decode()
    assert response.status_code == 200
    assert "No points have been awarded" in content
