from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, Semester, Student
from housepoints.models import Award


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
            "description": "Attendance on 2025-01-15 for Math Class",
            "students": [student1.pk, student2.pk],
        },
    )

    assert response.status_code == 200
    assert Award.objects.count() == 2

    alice_award = Award.objects.get(student=student1)
    # With default threshold of 14 and 0 prior attendance, should get 5 points
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
            "students": [present_student.pk],  # Bob is not selected (absent)
        },
    )

    assert response.status_code == 200
    assert Award.objects.count() == 1
    assert Award.objects.filter(student=present_student).exists()
    assert not Award.objects.filter(student=absent_student).exists()


@pytest.mark.django_db
def test_attendance_bulk_dynamic_points_based_on_threshold():
    """Test that points are dynamically calculated based on total points threshold."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        house_points_class_threshold=1,  # points_threshold = 5: first attendance = 5, rest = 3
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

    # First attendance should be 5 points (0 prior pts < points_threshold of 5)
    client.post(url, {"course": course.pk, "students": [student.pk]})
    first_award = Award.objects.first()
    assert first_award.points == 5

    # Second attendance should be 3 points (5 prior pts >= points_threshold of 5)
    client.post(url, {"course": course.pk, "students": [student.pk]})
    second_award = Award.objects.order_by("-id").first()
    assert second_award.points == 3


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
            "students": [unenrolled_student.pk],
        },
    )

    # No awards should be created for unenrolled students
    assert Award.objects.count() == 0


# ============================================================================
# Dynamic Attendance Points Tests
# ============================================================================


@pytest.mark.django_db
def test_semester_has_house_points_class_threshold():
    """Test that semester has the house_points_class_threshold field with default 14."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    assert semester.house_points_class_threshold == 14


@pytest.mark.django_db
def test_semester_custom_house_points_class_threshold():
    """Test that semester can have a custom threshold."""
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        house_points_class_threshold=10,
    )

    assert semester.house_points_class_threshold == 10


@pytest.mark.django_db
def test_attendance_bulk_awards_5_points_below_threshold():
    """Test that students below points threshold get 5 points."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        house_points_class_threshold=3,  # points_threshold = 15
    )
    course = Course.objects.create(
        name="Math Class",
        description="Test",
        semester=semester,
    )

    user1 = User.objects.create_user(username="alice", password="password")
    student = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    course.students.add(student)

    # Student has 0 prior points, should get 5 points (0 < 15)
    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "description": "Week 1",
            "students": [student.pk],
        },
    )

    assert response.status_code == 200
    assert Award.objects.count() == 1
    award = Award.objects.first()
    assert award.points == 5


@pytest.mark.django_db
def test_attendance_bulk_awards_3_points_at_threshold():
    """Test that students at or above points threshold get 3 points."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        house_points_class_threshold=2,  # points_threshold = 10
    )
    course = Course.objects.create(
        name="Math Class",
        description="Test",
        semester=semester,
    )

    user1 = User.objects.create_user(username="alice", password="password")
    student = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    course.students.add(student)

    # Create 2 prior attendance awards with 5 pts each = 10 pts total (at points_threshold)
    for i in range(2):
        Award.objects.create(
            semester=semester,
            student=student,
            award_type=Award.AwardType.CLASS_ATTENDANCE,
            points=5,
            description=f"Week {i + 1}",
        )

    # Student has 10 prior pts (at points_threshold of 10), should get 3 points
    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "description": "Week 3",
            "students": [student.pk],
        },
    )

    assert response.status_code == 200
    assert Award.objects.count() == 3
    # Get the most recent award
    latest_award = Award.objects.order_by("-id").first()
    assert latest_award.points == 3


@pytest.mark.django_db
def test_attendance_bulk_mixed_threshold_students():
    """Test awarding points to students with different prior total points."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        house_points_class_threshold=2,  # points_threshold = 10
    )
    course = Course.objects.create(
        name="Math Class",
        description="Test",
        semester=semester,
    )

    user1 = User.objects.create_user(username="alice", password="password")
    user2 = User.objects.create_user(username="bob", password="password")

    # Student 1: no prior points (should get 5 pts)
    student1 = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice (New)",
    )

    # Student 2: 10 prior pts (at points_threshold of 10, should get 3 pts)
    student2 = Student.objects.create(
        user=user2,
        semester=semester,
        house=Student.House.CAT,
        airtable_name="Bob (Veteran)",
    )
    for i in range(2):
        Award.objects.create(
            semester=semester,
            student=student2,
            award_type=Award.AwardType.CLASS_ATTENDANCE,
            points=5,
            description=f"Prior week {i + 1}",
        )

    course.students.add(student1, student2)

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "description": "This week",
            "students": [student1.pk, student2.pk],
        },
    )

    assert response.status_code == 200
    # 2 prior + 2 new = 4 awards
    assert Award.objects.count() == 4

    # Check student1 got 5 points
    student1_award = Award.objects.filter(
        student=student1, description="This week"
    ).first()
    assert student1_award.points == 5

    # Check student2 got 3 points
    student2_award = Award.objects.filter(
        student=student2, description="This week"
    ).first()
    assert student2_award.points == 3


@pytest.mark.django_db
def test_attendance_bulk_shows_total_points_and_calculated_points():
    """Test that load students shows total prior points and calculated points."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        house_points_class_threshold=2,  # points_threshold = 10
    )
    course = Course.objects.create(
        name="Test Course",
        description="Test",
        semester=semester,
    )

    user1 = User.objects.create_user(username="alice", password="password")
    student = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    # Create 1 prior attendance with 5 pts (below points_threshold of 10)
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=5,
        description="Prior week",
    )
    course.students.add(student)

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "load_students": "1",
        },
    )

    content = response.content.decode()
    assert response.status_code == 200
    assert "Alice Smith" in content
    # Should show +5 pts (since 5 prior pts < points_threshold of 10)
    assert "+5 pts" in content
    # Should show prior total points
    assert "5 pts prior" in content


@pytest.mark.django_db
def test_attendance_bulk_threshold_boundary():
    """Test boundary behavior: below points_threshold gets 5pts, at/above gets 3pts."""
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        house_points_class_threshold=3,  # points_threshold = 15
    )
    course = Course.objects.create(
        name="Math Class",
        description="Test",
        semester=semester,
    )

    user1 = User.objects.create_user(username="alice", password="password")
    student = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    course.students.add(student)

    # Create 2 prior attendance awards with 5 pts each = 10 pts total
    for i in range(2):
        Award.objects.create(
            semester=semester,
            student=student,
            award_type=Award.AwardType.CLASS_ATTENDANCE,
            points=5,
            description=f"Week {i + 1}",
        )

    # At 10 pts (below points_threshold of 15), should still get 5 points
    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    client.post(
        url,
        {
            "course": course.pk,
            "description": "Week 3",
            "students": [student.pk],
        },
    )

    # Now at 15 pts (at points_threshold), next one should get 3 points
    client.post(
        url,
        {
            "course": course.pk,
            "description": "Week 4",
            "students": [student.pk],
        },
    )

    awards = list(Award.objects.filter(student=student).order_by("id"))
    assert len(awards) == 4
    # First 3 should be 5 points (total accumulates: 0->5->10->15)
    assert awards[0].points == 5
    assert awards[1].points == 5
    assert awards[2].points == 5
    # 4th should be 3 points (15 pts prior >= points_threshold of 15)
    assert awards[3].points == 3


@pytest.mark.django_db
def test_attendance_bulk_legacy_import_bundled_points():
    """Test that legacy imports with bundled points are handled correctly.

    Legacy imports may bundle multiple attendances into a single award with
    higher points (e.g., one award with 25 pts instead of five awards with 5 pts each).
    The logic should use total points, not attendance count.
    """
    client = Client()
    User.objects.create_user(username="staff", password="password", is_staff=True)

    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
        house_points_class_threshold=3,  # points_threshold = 15
    )
    course = Course.objects.create(
        name="Math Class",
        description="Test",
        semester=semester,
    )

    user1 = User.objects.create_user(username="alice", password="password")
    student = Student.objects.create(
        user=user1,
        semester=semester,
        house=Student.House.OWL,
        airtable_name="Alice Smith",
    )
    course.students.add(student)

    # Create a single legacy award with 20 pts (simulating bundled import)
    # This is above points_threshold of 15, so new attendance should get 3 pts
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=20,
        description="Legacy import - bundled attendances",
    )

    client.login(username="staff", password="password")
    url = reverse("housepoints:attendance_bulk")
    response = client.post(
        url,
        {
            "course": course.pk,
            "description": "New attendance",
            "students": [student.pk],
        },
    )

    assert response.status_code == 200
    assert Award.objects.count() == 2
    # Despite only 1 prior award, the new one should get 3 pts (20 prior pts >= 15)
    new_award = Award.objects.order_by("-id").first()
    assert new_award.points == 3
