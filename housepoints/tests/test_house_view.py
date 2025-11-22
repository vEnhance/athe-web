from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Semester, Student
from housepoints.models import Award

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
