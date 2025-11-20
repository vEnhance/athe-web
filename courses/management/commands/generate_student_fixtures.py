import random
from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from courses.models import Course, Semester, Student

User = get_user_model()


class Command(BaseCommand):
    help = "Generate 100 sample students for Fall Session 2025"

    def add_arguments(self, parser):  # type: ignore[no-untyped-def]
        parser.add_argument(
            "--count",
            type=int,
            default=100,
            help="Number of students to generate (default: 100)",
        )
        parser.add_argument(
            "--semester-slug",
            type=str,
            default="fall-25",
            help="Semester slug (default: fall-25)",
        )
        parser.add_argument(
            "--courses-per-student-min",
            type=int,
            default=1,
            help="Minimum courses per student (default: 1)",
        )
        parser.add_argument(
            "--courses-per-student-max",
            type=int,
            default=4,
            help="Maximum courses per student (default: 4)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        count = options["count"]
        semester_slug = options["semester_slug"]
        courses_per_student_min = options["courses_per_student_min"]
        courses_per_student_max = options["courses_per_student_max"]

        # Get the semester
        try:
            semester = Semester.objects.get(slug=semester_slug)
        except Semester.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Semester with slug '{semester_slug}' not found")
            )
            return

        # Get all courses for this semester
        courses = list(Course.objects.filter(semester=semester))
        if not courses:
            self.stdout.write(
                self.style.ERROR(f"No courses found for semester {semester}")
            )
            return

        # Get all houses
        houses = [choice[0] for choice in Student.House.choices]

        self.stdout.write(
            self.style.SUCCESS(
                f"Generating {count} students for {semester} "
                f"with {len(courses)} courses and {len(houses)} houses"
            )
        )

        created_users = 0
        created_students = 0

        with transaction.atomic():
            for i in range(count):
                student_num = i + 1
                username = f"student{student_num:03d}"
                email = f"{username}@example.com"
                first_name = "Student"
                last_name = f"#{student_num:03d}"

                # Check if user already exists
                if User.objects.filter(username=username).exists():
                    self.stdout.write(
                        self.style.WARNING(f"User {username} already exists, skipping")
                    )
                    continue

                # Create user with a default password
                user = User.objects.create_user(  # type: ignore[attr-defined]
                    username=username,
                    email=email,
                    password="athemath2025",  # Default password for all test users
                    first_name=first_name,
                    last_name=last_name,
                )
                created_users += 1

                # Assign house (evenly distributed)
                house = houses[i % len(houses)]

                # Create student
                student = Student.objects.create(
                    user=user, semester=semester, house=house
                )

                # Randomly assign courses
                num_courses = random.randint(
                    courses_per_student_min, courses_per_student_max
                )
                selected_courses = random.sample(
                    courses, min(num_courses, len(courses))
                )
                student.enrolled_courses.set(selected_courses)

                created_students += 1

                if (student_num) % 10 == 0:
                    self.stdout.write(f"Created {student_num} students...")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nSuccessfully created {created_users} users and {created_students} students!"
            )
        )
        self.stdout.write(
            self.style.SUCCESS("Default password for all students: athemath2025")
        )

        # Print summary by house
        self.stdout.write("\nStudents per house:")
        for house_code, house_name in Student.House.choices:
            house_count = Student.objects.filter(
                semester=semester, house=house_code
            ).count()
            self.stdout.write(f"  {house_name}: {house_count} students")

        # Print summary by course
        self.stdout.write("\nStudents per course:")
        for course in courses:
            course_count = course.enrolled_students.filter(semester=semester).count()  # type: ignore[attr-defined]
            self.stdout.write(f"  {course.name}: {course_count} students")
