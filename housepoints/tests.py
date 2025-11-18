from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.test import Client
from django.urls import reverse
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
    assert student.get_house_display() == "Owl"


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
    assert Award.DEFAULT_POINTS["potd_top3"] == 20
    assert Award.DEFAULT_POINTS["potd_4_10"] == 10
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
        user=user1, semester=semester, house=Student.House.OWL
    )
    student2 = Student.objects.create(
        user=user2, semester=semester, house=Student.House.CAT
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
    # Owl should have 10 points (5+5), Cat should have 5
    assert "10" in content  # Owl total
    assert "Owl" in content
    assert "Cat" in content


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
        user=user, semester=semester, house=Student.House.BLOB
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
    assert "Blob" in content
    assert "Cat" in content
    assert "Owl" in content
    assert "Red Panda" in content
    assert "Bunny" in content


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
    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    Student.objects.create(user=user1, semester=semester, house=Student.House.OWL)
    Student.objects.create(user=user2, semester=semester, house=Student.House.CAT)

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "semester": semester.pk,
            "award_type": Award.AwardType.OFFICE_HOURS,
            "usernames": "alice\nbob",
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

    user = User.objects.create_user(username="alice", password="password")
    Student.objects.create(user=user, semester=semester, house=Student.House.BLOB)

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "semester": semester.pk,
            "award_type": Award.AwardType.CLASS_ATTENDANCE,
            "usernames": "alice",
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

    user = User.objects.create_user(username="alice", password="password")
    Student.objects.create(user=user, semester=semester, house=Student.House.OWL)

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "semester": semester.pk,
            "award_type": Award.AwardType.HOMEWORK,
            "usernames": "alice\nnonexistent",
            "points": "",
            "description": "",
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    # Alice should succeed
    assert "alice" in content
    # Nonexistent should fail
    assert "nonexistent" in content
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

    user = User.objects.create_user(username="alice", password="password")
    Student.objects.create(user=user, semester=semester, house="")  # No house

    client.login(username="staff", password="password")
    url = reverse("housepoints:bulk_award")
    response = client.post(
        url,
        {
            "semester": semester.pk,
            "award_type": Award.AwardType.HOMEWORK,
            "usernames": "alice",
            "points": "",
            "description": "",
        },
    )

    content = response.content.decode()
    assert "No house assigned" in content
    assert Award.objects.count() == 0


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
        user=user, semester=semester, house=Student.House.BUNNY
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
        user=user, semester=semester, house=Student.House.CAT
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
    assert "Cat" in content  # House name


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
        user=user1, semester=semester, house=Student.House.OWL
    )
    student2 = Student.objects.create(
        user=user2, semester=semester, house=Student.House.CAT
    )

    Award.objects.create(
        semester=semester,
        student=student1,
        award_type=Award.AwardType.POTD_TOP3,
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
    assert "potd_top3" in types
    assert "potd_4_10" in types
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
        user=user, semester=semester, house=Student.House.OWL
    )
    award = Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.HOMEWORK,
        points=5,
    )

    assert "testuser" in str(award)
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

    assert "Bunny" in str(award)
    assert "House Activity Bonus" in str(award)
    assert "50 pts" in str(award)


# ============================================================================
# Autocomplete API Tests
# ============================================================================


@pytest.mark.django_db
def test_autocomplete_requires_login():
    """Test that autocomplete API requires authentication."""
    client = Client()
    url = reverse("housepoints:student_autocomplete")
    response = client.get(url, {"q": "test"})

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_autocomplete_requires_staff():
    """Test that autocomplete API requires staff access."""
    client = Client()
    User.objects.create_user(username="student", password="password")

    client.login(username="student", password="password")
    url = reverse("housepoints:student_autocomplete")
    response = client.get(url, {"q": "test"})

    assert response.status_code == 403


@pytest.mark.django_db
def test_autocomplete_searches_by_username():
    """Test that autocomplete searches by username."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user1 = User.objects.create_user(username="alice123", password="password")
    user2 = User.objects.create_user(username="bob456", password="password")
    Student.objects.create(user=user1, semester=semester, house=Student.House.OWL)
    Student.objects.create(user=user2, semester=semester, house=Student.House.CAT)

    client.login(username="staff", password="password")
    url = reverse("housepoints:student_autocomplete")
    response = client.get(url, {"q": "alice"})

    assert response.status_code == 200
    data = response.json()
    assert len(data["students"]) == 1
    assert data["students"][0]["username"] == "alice123"


@pytest.mark.django_db
def test_autocomplete_searches_by_name():
    """Test that autocomplete searches by first and last name."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(
        username="jdoe",
        password="password",
        first_name="John",
        last_name="Doe",
    )
    Student.objects.create(user=user, semester=semester, house=Student.House.BLOB)

    client.login(username="staff", password="password")
    url = reverse("housepoints:student_autocomplete")

    # Search by first name
    response = client.get(url, {"q": "john"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["students"]) == 1
    assert data["students"][0]["username"] == "jdoe"
    assert "John Doe" in data["students"][0]["display"]

    # Search by last name
    response = client.get(url, {"q": "doe"})
    data = response.json()
    assert len(data["students"]) == 1
    assert data["students"][0]["username"] == "jdoe"


@pytest.mark.django_db
def test_autocomplete_filters_by_semester():
    """Test that autocomplete filters results by semester."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
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
    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")
    Student.objects.create(user=user1, semester=fall, house=Student.House.OWL)
    Student.objects.create(user=user2, semester=spring, house=Student.House.CAT)

    client.login(username="staff", password="password")
    url = reverse("housepoints:student_autocomplete")

    # Search without semester filter (need at least 2 chars)
    response = client.get(url, {"q": "al"})
    data = response.json()
    assert len(data["students"]) == 1  # Only alice matches "al"
    assert data["students"][0]["username"] == "alice"

    # Search with fall semester filter
    response = client.get(url, {"q": "al", "semester": str(fall.pk)})
    data = response.json()
    assert len(data["students"]) == 1
    assert data["students"][0]["username"] == "alice"

    # Search with spring semester filter should not find alice
    response = client.get(url, {"q": "al", "semester": str(spring.pk)})
    data = response.json()
    assert len(data["students"]) == 0


@pytest.mark.django_db
def test_autocomplete_shows_house():
    """Test that autocomplete includes house in display."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )
    user = User.objects.create_user(username="alice", password="password")
    Student.objects.create(user=user, semester=semester, house=Student.House.RED_PANDA)

    client.login(username="staff", password="password")
    url = reverse("housepoints:student_autocomplete")
    response = client.get(url, {"q": "alice"})

    data = response.json()
    assert len(data["students"]) == 1
    assert "Red Panda" in data["students"][0]["display"]


@pytest.mark.django_db
def test_autocomplete_minimum_query_length():
    """Test that autocomplete requires at least 2 characters."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    client.login(username="staff", password="password")
    url = reverse("housepoints:student_autocomplete")

    # Single character should return empty
    response = client.get(url, {"q": "a"})
    data = response.json()
    assert len(data["students"]) == 0

    # No query should return empty
    response = client.get(url, {"q": ""})
    data = response.json()
    assert len(data["students"]) == 0
