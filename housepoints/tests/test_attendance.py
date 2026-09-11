from collections.abc import Callable
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from atheweb.testsuite import AtheClient
from courses.models import Course, Semester, Student
from housepoints.models import Award

ATTENDANCE = reverse("housepoints:attendance_bulk")


@pytest.fixture
def staff(athe: AtheClient, make_user: Callable[..., User]) -> User:
    return athe.login(make_user(username="staff", is_staff=True))


@pytest.fixture
def course(semester: Semester, make_course: Callable[..., Course]) -> Course:
    return make_course(semester, name="Math Class")


def choices(response) -> list[str]:
    return [
        course.name for course in response.context["form"].fields["course"].queryset
    ]


def loaded(response) -> dict[str, tuple[int, int]]:
    """Each loaded student's prior total and the points this session would give."""
    return {
        item["student"].airtable_name: (item["total_points"], item["points"])
        for item in response.context["students"]
    }


def prior_attendance(semester: Semester, student: Student, points: int) -> None:
    Award.objects.create(
        semester=semester,
        student=student,
        award_type=Award.AwardType.CLASS_ATTENDANCE,
        points=points,
    )


@pytest.mark.django_db
def test_attendance_bulk_requires_staff(
    athe: AtheClient, make_user: Callable[..., User]
):
    athe.login(make_user())
    assert athe.get(ATTENDANCE).status_code == 403


@pytest.mark.django_db
def test_attendance_bulk_staff_access(athe: AtheClient, staff: User):
    response = athe.get_ok(ATTENDANCE)

    assert response.context["students"] == []
    assert response.context["results"] is None


@pytest.mark.django_db
def test_attendance_bulk_shows_active_semester_courses(
    athe: AtheClient,
    staff: User,
    semester: Semester,
    make_semester: Callable[..., Semester],
    make_course: Callable[..., Course],
):
    make_course(semester, name="Active Course")
    today = timezone.localdate()
    ended = make_semester(
        name="Spring 2020",
        start_date=today - timedelta(days=200),
        end_date=today - timedelta(days=110),
    )
    make_course(ended, name="Ended Course")

    assert choices(athe.get_ok(ATTENDANCE)) == ["Active Course"]


@pytest.mark.django_db
def test_attendance_bulk_excludes_clubs(
    athe: AtheClient,
    staff: User,
    semester: Semester,
    make_course: Callable[..., Course],
):
    make_course(semester, name="Regular Class")
    make_course(semester, name="Test Club", is_club=True)

    assert choices(athe.get_ok(ATTENDANCE)) == ["Regular Class"]


@pytest.mark.django_db
def test_attendance_bulk_default_course_for_leader(
    athe: AtheClient,
    staff: User,
    semester: Semester,
    make_course: Callable[..., Course],
    make_staff_listing,
):
    """The dropdown opens on a class this staff member teaches."""
    make_course(semester, name="Other Course")
    led = make_course(semester, name="Led Course", instructor=make_staff_listing(staff))

    response = athe.get_ok(ATTENDANCE)

    assert response.context["form"].fields["course"].initial == led


@pytest.mark.django_db
def test_attendance_bulk_load_students(
    athe: AtheClient,
    staff: User,
    semester: Semester,
    course: Course,
    make_student: Callable[..., Student],
):
    alice = make_student(semester, house=Student.House.OWL, airtable_name="Alice Smith")
    bob = make_student(semester, house=Student.House.CAT, airtable_name="Bob Jones")
    course.students.add(alice, bob)

    response = athe.post_ok(ATTENDANCE, {"course": course.pk, "load_students": "1"})

    assert response.context["selected_course"] == course
    assert loaded(response) == {"Alice Smith": (0, 5), "Bob Jones": (0, 5)}
    athe.assert_testid_count(response, "attendance-student", 2)


@pytest.mark.django_db
def test_attendance_bulk_excludes_students_without_house(
    athe: AtheClient,
    staff: User,
    semester: Semester,
    course: Course,
    make_student: Callable[..., Student],
):
    housed = make_student(semester, house=Student.House.OWL, airtable_name="Alice")
    unhoused = make_student(semester, house="", airtable_name="Bob NoHouse")
    course.students.add(housed, unhoused)

    response = athe.post_ok(ATTENDANCE, {"course": course.pk, "load_students": "1"})

    assert list(loaded(response)) == ["Alice"]


@pytest.mark.django_db
def test_attendance_bulk_shows_prior_and_calculated_points(
    athe: AtheClient,
    staff: User,
    make_semester: Callable[..., Semester],
    make_course: Callable[..., Course],
    make_student: Callable[..., Student],
):
    """The threshold is in points, not sessions, so both numbers are shown."""
    semester = make_semester(house_points_class_threshold=2)
    course = make_course(semester)
    student = make_student(semester, house=Student.House.OWL, airtable_name="Alice")
    course.students.add(student)
    prior_attendance(semester, student, 5)

    response = athe.post_ok(ATTENDANCE, {"course": course.pk, "load_students": "1"})

    assert response.context["points_threshold"] == 10
    assert loaded(response) == {"Alice": (5, 5)}


@pytest.mark.django_db
def test_attendance_bulk_creates_awards(
    athe: AtheClient,
    staff: User,
    semester: Semester,
    course: Course,
    make_student: Callable[..., Student],
):
    alice = make_student(semester, house=Student.House.OWL, airtable_name="Alice Smith")
    bob = make_student(semester, house=Student.House.CAT, airtable_name="Bob Jones")
    course.students.add(alice, bob)

    response = athe.post_ok(
        ATTENDANCE,
        {
            "course": course.pk,
            "description": "Attendance on 2025-01-15 for Math Class",
            "students": [alice.pk, bob.pk],
        },
    )

    assert Award.objects.count() == 2
    alice_award = Award.objects.get(student=alice)
    assert alice_award.points == 5
    assert alice_award.house == Student.House.OWL
    assert alice_award.award_type == Award.AwardType.CLASS_ATTENDANCE
    assert alice_award.awarded_by == staff
    assert alice_award.description == "Attendance on 2025-01-15 for Math Class"
    assert Award.objects.get(student=bob).house == Student.House.CAT
    athe.assert_testid(response, "attendance-awarded")
    athe.assert_no_testid(response, "attendance-errors")


@pytest.mark.django_db
def test_attendance_bulk_partial_selection(
    athe: AtheClient,
    staff: User,
    semester: Semester,
    course: Course,
    make_student: Callable[..., Student],
):
    """Unchecked students are the absent ones, and get nothing."""
    present = make_student(semester, house=Student.House.OWL)
    absent = make_student(semester, house=Student.House.CAT)
    course.students.add(present, absent)

    athe.post_ok(ATTENDANCE, {"course": course.pk, "students": [present.pk]})

    assert list(Award.objects.values_list("student", flat=True)) == [present.pk]


@pytest.mark.django_db
def test_attendance_bulk_no_students_selected(
    athe: AtheClient, staff: User, course: Course
):
    response = athe.post_ok(ATTENDANCE, {"course": course.pk})

    assert Award.objects.count() == 0
    assert len(response.context["results"].errors) == 1
    athe.assert_testid(response, "attendance-errors")


@pytest.mark.django_db
def test_attendance_bulk_validates_student_enrollment(
    athe: AtheClient,
    staff: User,
    semester: Semester,
    course: Course,
    make_student: Callable[..., Student],
):
    """A student who is not in the class cannot be awarded for attending it."""
    outsider = make_student(semester, house=Student.House.OWL)

    athe.post_ok(ATTENDANCE, {"course": course.pk, "students": [outsider.pk]})

    assert Award.objects.count() == 0


@pytest.mark.django_db
def test_semester_house_points_class_threshold_defaults_to_14(semester: Semester):
    assert semester.house_points_class_threshold == 14


@pytest.mark.django_db
def test_attendance_points_drop_at_the_threshold(
    athe: AtheClient,
    staff: User,
    make_semester: Callable[..., Semester],
    make_course: Callable[..., Course],
    make_student: Callable[..., Student],
):
    """Attendance is worth 5 points until the student has the threshold's worth
    of them, and 3 points after: 14 classes at 5 points is 70."""
    semester = make_semester(house_points_class_threshold=3)
    course = make_course(semester)
    student = make_student(semester, house=Student.House.OWL)
    course.students.add(student)

    for _ in range(4):
        athe.post_ok(ATTENDANCE, {"course": course.pk, "students": [student.pk]})

    points = list(Award.objects.order_by("pk").values_list("points", flat=True))
    assert points == [5, 5, 5, 3]


@pytest.mark.django_db
def test_attendance_points_are_per_student(
    athe: AtheClient,
    staff: User,
    make_semester: Callable[..., Semester],
    make_course: Callable[..., Course],
    make_student: Callable[..., Student],
):
    """Two students in the same class can be either side of the threshold."""
    semester = make_semester(house_points_class_threshold=2)
    course = make_course(semester)
    newcomer = make_student(semester, house=Student.House.OWL)
    veteran = make_student(semester, house=Student.House.CAT)
    course.students.add(newcomer, veteran)
    prior_attendance(semester, veteran, 10)

    athe.post_ok(
        ATTENDANCE,
        {
            "course": course.pk,
            "description": "This week",
            "students": [newcomer.pk, veteran.pk],
        },
    )

    assert Award.objects.get(student=newcomer, description="This week").points == 5
    assert Award.objects.get(student=veteran, description="This week").points == 3


@pytest.mark.django_db
def test_attendance_points_count_points_not_awards(
    athe: AtheClient,
    staff: User,
    make_semester: Callable[..., Semester],
    make_course: Callable[..., Course],
    make_student: Callable[..., Student],
):
    """Legacy imports bundle a term's attendance into one award, so a single
    prior row can already put a student past the threshold."""
    semester = make_semester(house_points_class_threshold=3)
    course = make_course(semester)
    student = make_student(semester, house=Student.House.OWL)
    course.students.add(student)
    prior_attendance(semester, student, 20)

    athe.post_ok(
        ATTENDANCE,
        {
            "course": course.pk,
            "description": "New attendance",
            "students": [student.pk],
        },
    )

    assert Award.objects.get(description="New attendance").points == 3
