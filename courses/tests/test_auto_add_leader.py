from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from courses.models import Course, Semester
from home.models import StaffPhotoListing


@pytest.mark.django_db
def test_course_auto_adds_instructor_as_leader():
    """Test that creating a course with an instructor automatically adds them as a leader."""
    # Create a user and staff listing
    user = User.objects.create_user(username="instructor1", password="password")
    staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Dr. Smith",
        slug="dr-smith",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course with the instructor
    course = Course.objects.create(
        name="Advanced Math",
        description="Advanced math course",
        semester=semester,
        instructor=staff,
    )

    # Verify the instructor's user was automatically added as a leader
    assert user in course.leaders.all()
    assert course.leaders.count() == 1


@pytest.mark.django_db
def test_course_instructor_without_user_no_error():
    """Test that a course with an instructor that has no user doesn't cause errors."""
    # Create a staff listing without a user
    staff = StaffPhotoListing.objects.create(
        user=None,
        display_name="Dr. Jones",
        slug="dr-jones",
        role="Guest Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course with the instructor (should not raise an error)
    course = Course.objects.create(
        name="Guest Lecture",
        description="Special guest lecture",
        semester=semester,
        instructor=staff,
    )

    # Verify no leaders were added
    assert course.leaders.count() == 0


@pytest.mark.django_db
def test_course_without_instructor_no_error():
    """Test that a course without an instructor doesn't cause errors."""
    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course without an instructor
    course = Course.objects.create(
        name="Self-Study Course",
        description="Self-paced learning",
        semester=semester,
        instructor=None,
    )

    # Verify no leaders were added
    assert course.leaders.count() == 0


@pytest.mark.django_db
def test_course_update_instructor_adds_leader():
    """Test that updating a course to add an instructor automatically adds them as a leader."""
    # Create a user and staff listing
    user = User.objects.create_user(username="instructor2", password="password")
    staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Dr. Brown",
        slug="dr-brown",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course without an instructor
    course = Course.objects.create(
        name="Physics 101",
        description="Basic physics",
        semester=semester,
    )

    # Verify no leaders initially
    assert course.leaders.count() == 0

    # Update the course to add an instructor
    course.instructor = staff
    course.save()

    # Verify the instructor's user was automatically added as a leader
    assert user in course.leaders.all()
    assert course.leaders.count() == 1


@pytest.mark.django_db
def test_course_instructor_idempotent():
    """Test that saving a course multiple times doesn't duplicate the leader."""
    # Create a user and staff listing
    user = User.objects.create_user(username="instructor3", password="password")
    staff = StaffPhotoListing.objects.create(
        user=user,
        display_name="Dr. Lee",
        slug="dr-lee",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course with the instructor
    course = Course.objects.create(
        name="Chemistry 101",
        description="Basic chemistry",
        semester=semester,
        instructor=staff,
    )

    # Verify the leader was added
    assert course.leaders.count() == 1
    assert user in course.leaders.all()

    # Save the course again
    course.save()

    # Verify the leader count didn't increase
    assert course.leaders.count() == 1
    assert user in course.leaders.all()


@pytest.mark.django_db
def test_course_change_instructor_adds_new_leader():
    """Test that changing the instructor adds the new instructor as a leader."""
    # Create two users and staff listings
    user1 = User.objects.create_user(username="instructor4", password="password")
    staff1 = StaffPhotoListing.objects.create(
        user=user1,
        display_name="Dr. Taylor",
        slug="dr-taylor",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test.jpg",
    )

    user2 = User.objects.create_user(username="instructor5", password="password")
    staff2 = StaffPhotoListing.objects.create(
        user=user2,
        display_name="Dr. Wilson",
        slug="dr-wilson",
        role="Instructor",
        category="instructor",
        biography="Test bio",
        photo="staff_photos/test2.jpg",
    )

    # Create a semester
    semester = Semester.objects.create(
        name="Fall 2025",
        slug="fa25",
        start_date=timezone.now().date(),
        end_date=(timezone.now() + timedelta(days=90)).date(),
    )

    # Create a course with the first instructor
    course = Course.objects.create(
        name="Biology 101",
        description="Basic biology",
        semester=semester,
        instructor=staff1,
    )

    # Verify the first instructor is a leader
    assert user1 in course.leaders.all()
    assert course.leaders.count() == 1

    # Change the instructor
    course.instructor = staff2
    course.save()

    # Verify both instructors are now leaders (old one remains, new one is added)
    assert user1 in course.leaders.all()
    assert user2 in course.leaders.all()
    assert course.leaders.count() == 2
