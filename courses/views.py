from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView

from courses.forms import CourseMeetingForm
from courses.models import Course, CourseMeeting, Semester, Student


def catalog_root(request: HttpRequest) -> HttpResponse:
    """Show the most recent semester as the main catalog landing page."""
    # Get the most recent semester (by start_date)
    latest_semester = Semester.objects.order_by("-start_date").first()
    if latest_semester:
        return redirect("courses:course_list", slug=latest_semester.slug)
    return render(request, "courses/semester_list.html", {"semesters": []})


def semester_list(request: HttpRequest) -> HttpResponse:
    """Show all semesters in chronological order."""
    semesters = Semester.objects.order_by("-start_date")
    return render(request, "courses/semester_list.html", {"semesters": semesters})


def course_list(request: HttpRequest, slug: str) -> HttpResponse:
    """Show courses for a specific semester with previous/next navigation."""
    semester = get_object_or_404(Semester, slug=slug)
    # Filter to only show classes (not clubs)
    courses = Course.objects.filter(semester=semester, is_club=False).select_related(
        "instructor"
    )

    # Get previous and next semesters
    prev_semester = (
        Semester.objects.filter(start_date__lt=semester.start_date)
        .order_by("-start_date")
        .first()
    )
    next_semester = (
        Semester.objects.filter(start_date__gt=semester.start_date)
        .order_by("start_date")
        .first()
    )

    return render(
        request,
        "courses/course_list.html",
        {
            "semester": semester,
            "courses": courses,
            "prev_semester": prev_semester,
            "next_semester": next_semester,
        },
    )


@login_required
def my_courses(request: HttpRequest) -> HttpResponse:
    """Show all courses (non-clubs) the current user is enrolled in or leads."""
    # Get all student records for this user
    student_records = Student.objects.filter(user=request.user).prefetch_related(
        "enrolled_courses__semester", "enrolled_courses__instructor"
    )

    # Collect all enrolled courses (non-clubs only)
    enrolled_course_ids = set()
    for student in student_records:
        for course in student.enrolled_courses.filter(is_club=False):
            enrolled_course_ids.add(course.id)  # type: ignore[attr-defined]

    # Get all courses where user is a leader (non-clubs only)
    led_courses = Course.objects.filter(
        leaders=request.user, is_club=False
    ).select_related("semester", "instructor")

    # Combine enrolled and led courses (avoid duplicates)
    all_courses = {}
    for student in student_records:
        for course in student.enrolled_courses.filter(is_club=False):
            all_courses[course.id] = course  # type: ignore[attr-defined]
    for course in led_courses:
        all_courses[course.id] = course  # type: ignore[attr-defined]

    # Convert to list and sort
    enrolled_courses = list(all_courses.values())
    enrolled_courses.sort(key=lambda c: (-c.semester.start_date.toordinal(), c.name))

    return render(
        request,
        "courses/my_courses.html",
        {"enrolled_courses": enrolled_courses},
    )


@login_required
def my_clubs(request: HttpRequest) -> HttpResponse:
    """Show clubs in active semesters, split by enrollment status. Includes led clubs."""
    # Get user's student records for active semesters
    today = date.today()
    active_student_records = Student.objects.filter(
        user=request.user,
        semester__start_date__lte=today,
        semester__end_date__gte=today,
    ).prefetch_related("enrolled_courses", "semester")

    # Get all clubs where user is a leader (in active semesters)
    led_clubs = Course.objects.filter(
        leaders=request.user,
        is_club=True,
        semester__start_date__lte=today,
        semester__end_date__gte=today,
    ).select_related("semester", "instructor")

    if not active_student_records.exists() and not led_clubs.exists():
        return render(
            request,
            "courses/my_clubs.html",
            {
                "enrolled_clubs": [],
                "available_clubs": [],
                "has_active_semester": False,
            },
        )

    # Get all clubs from active semesters where user has student access
    active_semesters = [s.semester for s in active_student_records]
    all_active_clubs = Course.objects.filter(
        semester__in=active_semesters, is_club=True
    ).select_related("semester", "instructor")

    # Split into enrolled and available
    enrolled_club_ids = set()
    for student in active_student_records:
        for course in student.enrolled_courses.filter(is_club=True):
            enrolled_club_ids.add(course.id)  # type: ignore[attr-defined]

    # Add led clubs to enrolled list
    for club in led_clubs:
        enrolled_club_ids.add(club.id)  # type: ignore[attr-defined]

    enrolled_clubs = [c for c in all_active_clubs if c.id in enrolled_club_ids]  # type: ignore[attr-defined]
    # Also include led clubs that might not be in active_semesters
    for club in led_clubs:
        if club.id not in [c.id for c in enrolled_clubs]:  # type: ignore[attr-defined]
            enrolled_clubs.append(club)

    available_clubs = [c for c in all_active_clubs if c.id not in enrolled_club_ids]  # type: ignore[attr-defined]

    return render(
        request,
        "courses/my_clubs.html",
        {
            "enrolled_clubs": enrolled_clubs,
            "available_clubs": available_clubs,
            "has_active_semester": True,
        },
    )


@login_required
def past_clubs(request: HttpRequest) -> HttpResponse:
    """Show clubs from past semesters that the user was enrolled in (readonly)."""
    # Get user's student records for past semesters
    today = date.today()
    past_student_records = Student.objects.filter(
        user=request.user, semester__end_date__lt=today
    ).prefetch_related("enrolled_courses__semester", "enrolled_courses__instructor")

    # Collect all past clubs
    past_clubs = []
    for student in past_student_records:
        for course in student.enrolled_courses.filter(is_club=True):
            past_clubs.append(course)

    # Sort by semester (most recent first), then by course name
    past_clubs.sort(key=lambda c: (-c.semester.start_date.toordinal(), c.name))

    return render(request, "courses/past_clubs.html", {"past_clubs": past_clubs})


@login_required
def join_club(request: HttpRequest, pk: int) -> HttpResponse:
    """Join a club if the user has student access to that semester."""
    club = get_object_or_404(Course, pk=pk, is_club=True)

    # Check if semester is active
    if not club.semester.is_active():
        messages.error(request, "This club's semester is not currently active.")
        return redirect("courses:my_clubs")

    # Get or create student record for this semester
    student, _ = Student.objects.get_or_create(
        user=request.user, semester=club.semester
    )

    # Check if already enrolled
    if student.enrolled_courses.filter(pk=club.pk).exists():
        messages.info(request, f"You are already enrolled in {club.name}.")
    else:
        student.enrolled_courses.add(club)
        messages.success(request, f"Successfully joined {club.name}!")

    return redirect("courses:my_clubs")


@login_required
def drop_club(request: HttpRequest, pk: int) -> HttpResponse:
    """Drop a club if the semester is still active."""
    club = get_object_or_404(Course, pk=pk, is_club=True)

    # Check if semester is active
    if not club.semester.is_active():
        messages.error(request, "This club's semester is not currently active.")
        return redirect("courses:my_clubs")

    try:
        student = Student.objects.get(user=request.user, semester=club.semester)
        if student.enrolled_courses.filter(pk=club.pk).exists():
            student.enrolled_courses.remove(club)
            messages.success(request, f"Successfully dropped {club.name}.")
        else:
            messages.info(request, f"You are not enrolled in {club.name}.")
    except Student.DoesNotExist:
        messages.error(request, "Student record not found.")

    return redirect("courses:my_clubs")


@login_required
def upcoming(request: HttpRequest) -> HttpResponse:
    """Show all upcoming meetings for courses/clubs the user is enrolled in or leads."""
    # Get all student records for this user
    student_records = Student.objects.filter(user=request.user).prefetch_related(
        "enrolled_courses"
    )

    # Collect all enrolled course IDs
    enrolled_course_ids = set()
    for student in student_records:
        for course in student.enrolled_courses.all():
            enrolled_course_ids.add(course.id)  # type: ignore[attr-defined]

    # Get all courses where user is a leader
    led_courses = Course.objects.filter(leaders=request.user)
    for course in led_courses:
        enrolled_course_ids.add(course.id)  # type: ignore[attr-defined]

    # Get all future meetings for those courses
    now = timezone.now()
    upcoming_meetings = (
        CourseMeeting.objects.filter(
            course_id__in=enrolled_course_ids, start_time__gte=now
        )
        .select_related("course", "course__semester")
        .order_by("start_time")
    )

    return render(
        request,
        "courses/upcoming.html",
        {"upcoming_meetings": upcoming_meetings},
    )


class CourseDetailView(UserPassesTestMixin, DetailView):
    """
    Detail view for a course or club.
    - For classes: accessible to staff or enrolled students
    - For clubs: accessible to staff or any student with access to that semester
    """

    model = Course
    template_name = "courses/course_detail.html"
    context_object_name = "course"

    def test_func(self) -> bool:
        """Check access permissions based on whether it's a club or class."""
        if not self.request.user.is_authenticated:
            return False
        assert isinstance(self.request.user, User)
        if self.request.user.is_staff:
            return True

        course = self.get_object()

        # Leaders always have access
        if course.leaders.filter(pk=self.request.user.pk).exists():
            return True

        if course.is_club:
            # For clubs: any student with access to this semester
            return Student.objects.filter(
                user=self.request.user, semester=course.semester
            ).exists()
        else:
            # For classes: only enrolled students
            return Student.objects.filter(
                user=self.request.user, enrolled_courses=course
            ).exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assert isinstance(self.request.user, User)

        context["meetings"] = CourseMeeting.objects.filter(course=self.object).order_by(
            "start_time"
        )
        context["next_meeting"] = (
            CourseMeeting.objects.filter(
                course=self.object, start_time__gt=timezone.now() - timedelta(hours=1)
            )
            .order_by("start_time")
            .first()
        )

        # Add member list
        context["members"] = (
            Student.objects.filter(enrolled_courses=self.object)
            .select_related("user")
            .order_by("user__username")
        )

        # Check if user is a leader
        context["is_leader"] = (
            self.request.user.is_staff
            or self.object.leaders.filter(pk=self.request.user.pk).exists()
        )

        # For clubs in active semesters, check if user can join/drop
        if self.object.is_club and self.object.semester.is_active():
            try:
                student = Student.objects.get(
                    user=self.request.user, semester=self.object.semester
                )
                context["is_enrolled"] = student.enrolled_courses.filter(
                    pk=self.object.pk
                ).exists()
                context["can_join_drop"] = True
            except Student.DoesNotExist:
                context["is_enrolled"] = False
                context["can_join_drop"] = False
        else:
            context["is_enrolled"] = False
            context["can_join_drop"] = False

        return context


@login_required
def manage_meetings(request: HttpRequest, pk: int) -> HttpResponse:
    """Manage meetings for a course. Only accessible to staff and course leaders."""
    course = get_object_or_404(Course, pk=pk)
    assert isinstance(request.user, User)

    # Check if user is staff or a leader
    is_leader = (
        request.user.is_staff or course.leaders.filter(pk=request.user.pk).exists()
    )
    if not is_leader:
        messages.error(request, "You don't have permission to manage this course.")
        return redirect("courses:course_detail", pk=course.pk)

    meetings = CourseMeeting.objects.filter(course=course).order_by("start_time")

    return render(
        request,
        "courses/manage_meetings.html",
        {"course": course, "meetings": meetings},
    )


@login_required
def add_meeting(request: HttpRequest, pk: int) -> HttpResponse:
    """Add a new meeting to a course. Only accessible to staff and course leaders."""
    course = get_object_or_404(Course, pk=pk)
    assert isinstance(request.user, User)

    # Check if user is staff or a leader
    is_leader = (
        request.user.is_staff or course.leaders.filter(pk=request.user.pk).exists()
    )
    if not is_leader:
        messages.error(request, "You don't have permission to manage this course.")
        return redirect("courses:course_detail", pk=course.pk)

    if request.method == "POST":
        form = CourseMeetingForm(request.POST)
        if form.is_valid():
            meeting = form.save(commit=False)
            meeting.course = course
            meeting.save()
            messages.success(request, "Meeting added successfully!")
            return redirect("courses:manage_meetings", pk=course.pk)
    else:
        form = CourseMeetingForm()

    return render(
        request, "courses/meeting_form.html", {"form": form, "course": course}
    )


@login_required
def edit_meeting(request: HttpRequest, pk: int, meeting_pk: int) -> HttpResponse:
    """Edit a meeting. Only accessible to staff and course leaders."""
    course = get_object_or_404(Course, pk=pk)
    meeting = get_object_or_404(CourseMeeting, pk=meeting_pk, course=course)
    assert isinstance(request.user, User)

    # Check if user is staff or a leader
    is_leader = (
        request.user.is_staff or course.leaders.filter(pk=request.user.pk).exists()
    )
    if not is_leader:
        messages.error(request, "You don't have permission to manage this course.")
        return redirect("courses:course_detail", pk=course.pk)

    if request.method == "POST":
        form = CourseMeetingForm(request.POST, instance=meeting)
        if form.is_valid():
            form.save()
            messages.success(request, "Meeting updated successfully!")
            return redirect("courses:manage_meetings", pk=course.pk)
    else:
        form = CourseMeetingForm(instance=meeting)

    return render(
        request,
        "courses/meeting_form.html",
        {"form": form, "course": course, "meeting": meeting},
    )


@login_required
def delete_meeting(request: HttpRequest, pk: int, meeting_pk: int) -> HttpResponse:
    """Delete a meeting. Only accessible to staff and course leaders."""
    course = get_object_or_404(Course, pk=pk)
    meeting = get_object_or_404(CourseMeeting, pk=meeting_pk, course=course)
    assert isinstance(request.user, User)

    # Check if user is staff or a leader
    is_leader = (
        request.user.is_staff or course.leaders.filter(pk=request.user.pk).exists()
    )
    if not is_leader:
        messages.error(request, "You don't have permission to manage this course.")
        return redirect("courses:course_detail", pk=course.pk)

    if request.method == "POST":
        meeting.delete()
        messages.success(request, "Meeting deleted successfully!")
        return redirect("courses:manage_meetings", pk=course.pk)

    return render(
        request,
        "courses/meeting_confirm_delete.html",
        {"course": course, "meeting": meeting},
    )
