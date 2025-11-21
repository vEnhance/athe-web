from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Prefetch
from django.forms import modelformset_factory
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, UpdateView, View

from courses.forms import CourseMeetingForm, CourseUpdateForm, SortingHatForm
from courses.models import Course, CourseMeeting, Semester, Student


def catalog_root(request: HttpRequest) -> HttpResponse:
    """Show the most recent semester as the main catalog landing page."""
    # Get the most recent semester (by start_date)
    # Non-staff users can only see visible semesters
    queryset = Semester.objects.order_by("-start_date")
    is_staff = getattr(request.user, "is_staff", False)
    if not is_staff:
        queryset = queryset.filter(visible=True)
    latest_semester = queryset.first()
    if latest_semester:
        return redirect("courses:course_list", slug=latest_semester.slug)
    return render(request, "courses/semester_list.html", {"semesters": []})


def semester_list(request: HttpRequest) -> HttpResponse:
    """Show all semesters in chronological order."""
    semesters = Semester.objects.order_by("-start_date")
    # Non-staff users can only see visible semesters
    is_staff = getattr(request.user, "is_staff", False)
    if not is_staff:
        semesters = semesters.filter(visible=True)
    return render(request, "courses/semester_list.html", {"semesters": semesters})


def course_list(request: HttpRequest, slug: str) -> HttpResponse:
    """Show courses for a specific semester with previous/next navigation."""
    # Non-staff users can only access visible semesters
    is_staff = getattr(request.user, "is_staff", False)
    if is_staff:
        semester = get_object_or_404(Semester, slug=slug)
    else:
        semester = get_object_or_404(Semester, slug=slug, visible=True)

    # Filter to only show classes (not clubs)
    courses = Course.objects.filter(semester=semester, is_club=False).select_related(
        "instructor"
    )

    # Get previous and next semesters (only visible ones for non-staff)
    prev_queryset = Semester.objects.filter(start_date__lt=semester.start_date)
    next_queryset = Semester.objects.filter(start_date__gt=semester.start_date)
    if not is_staff:
        prev_queryset = prev_queryset.filter(visible=True)
        next_queryset = next_queryset.filter(visible=True)

    prev_semester = prev_queryset.order_by("-start_date").first()
    next_semester = next_queryset.order_by("start_date").first()

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
    # Use Prefetch to filter enrolled courses at the database level
    student_records = Student.objects.filter(user=request.user).prefetch_related(
        Prefetch(
            "enrolled_courses",
            queryset=Course.objects.filter(is_club=False).select_related(
                "semester", "instructor"
            ),
            to_attr="non_club_courses",
        )
    )

    # Get all courses where user is a leader (non-clubs only)
    led_courses = Course.objects.filter(
        leaders=request.user, is_club=False
    ).select_related("semester", "instructor")

    # Combine enrolled and led courses (avoid duplicates)
    all_courses = {}
    for student in student_records:
        for course in student.non_club_courses:  # type: ignore[attr-defined]
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
    active_student_records = (
        Student.objects.filter(
            user=request.user,
            semester__start_date__lte=today,
            semester__end_date__gte=today,
        )
        .select_related("semester")
        .prefetch_related(
            Prefetch(
                "enrolled_courses",
                queryset=Course.objects.filter(is_club=True).select_related(
                    "semester", "instructor"
                ),
                to_attr="enrolled_club_list",
            )
        )
    )

    # Get all clubs where user is a leader (in active semesters)
    led_clubs = Course.objects.filter(
        leaders=request.user,
        is_club=True,
        semester__start_date__lte=today,
        semester__end_date__gte=today,
    ).select_related("semester", "instructor")

    # Convert to list for easier manipulation
    active_student_records_list = list(active_student_records)
    led_clubs_list = list(led_clubs)

    if not active_student_records_list and not led_clubs_list:
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
    active_semesters = [s.semester for s in active_student_records_list]
    all_active_clubs = Course.objects.filter(
        semester__in=active_semesters, is_club=True
    ).select_related("semester", "instructor")

    # Build set of enrolled club IDs
    enrolled_club_ids = set()
    for student in active_student_records_list:
        for course in student.enrolled_club_list:  # type: ignore[attr-defined]
            enrolled_club_ids.add(course.id)  # type: ignore[attr-defined]

    # Add led clubs to enrolled list
    for club in led_clubs_list:
        enrolled_club_ids.add(club.id)  # type: ignore[attr-defined]

    # Split into enrolled and available
    enrolled_clubs_dict = {}
    available_clubs = []
    for club in all_active_clubs:
        if club.id in enrolled_club_ids:  # type: ignore[attr-defined]
            enrolled_clubs_dict[club.id] = club  # type: ignore[attr-defined]
        else:
            available_clubs.append(club)

    # Also include led clubs that might not be in active_semesters
    for club in led_clubs_list:
        if club.id not in enrolled_clubs_dict:  # type: ignore[attr-defined]
            enrolled_clubs_dict[club.id] = club  # type: ignore[attr-defined]

    enrolled_clubs = list(enrolled_clubs_dict.values())

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
    ).prefetch_related(
        Prefetch(
            "enrolled_courses",
            queryset=Course.objects.filter(is_club=True).select_related(
                "semester", "instructor"
            ),
            to_attr="enrolled_club_list",
        )
    )

    # Collect all past clubs (avoid duplicates)
    past_clubs_dict = {}
    for student in past_student_records:
        for course in student.enrolled_club_list:  # type: ignore[attr-defined]
            past_clubs_dict[course.id] = course  # type: ignore[attr-defined]

    # Convert to list and sort by semester (most recent first), then by course name
    past_clubs = list(past_clubs_dict.values())
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
    if club.students.filter(pk=student.pk).exists():
        messages.info(request, f"You are already enrolled in {club.name}.")
    else:
        club.students.add(student)
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
        if club.students.filter(pk=student.pk).exists():
            club.students.remove(student)
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
        for course in student.enrolled_courses.all():  # type: ignore[attr-defined]
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

        course = self.get_object()

        # Staff users have access to everything
        if self.request.user.is_staff:
            return True

        # Non-staff users cannot access courses in invisible semesters
        if not course.semester.visible:
            return False

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
            return course.students.filter(user=self.request.user).exists()

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
        context["members"] = self.object.students.select_related("user").order_by(
            "user__username"
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
                context["is_enrolled"] = self.object.students.filter(
                    pk=student.pk
                ).exists()
                context["can_join_drop"] = True
            except Student.DoesNotExist:
                context["is_enrolled"] = False
                context["can_join_drop"] = False
        else:
            context["is_enrolled"] = False
            context["can_join_drop"] = False

        return context


class CourseUpdateView(UserPassesTestMixin, UpdateView):
    """
    Update view for editing course details.
    Only accessible to staff or course leaders.
    """

    model = Course
    form_class = CourseUpdateForm
    template_name = "courses/course_update.html"
    context_object_name = "course"

    def test_func(self) -> bool:
        """Check if user is staff or a leader of this course."""
        if not self.request.user.is_authenticated:
            return False
        assert isinstance(self.request.user, User)
        if self.request.user.is_staff:
            return True

        course = self.get_object()
        return course.leaders.filter(pk=self.request.user.pk).exists()

    def get_success_url(self) -> str:
        """Redirect back to the course detail page after successful update."""
        return reverse("courses:course_detail", kwargs={"pk": self.object.pk})

    def form_valid(self, form: CourseUpdateForm):
        """Add a success message when the form is saved."""
        messages.success(
            self.request, f"{self.object.name} has been updated successfully!"
        )
        return super().form_valid(form)


@login_required
def manage_meetings(request: HttpRequest, pk: int) -> HttpResponse:
    """Manage meetings for a course using inline formsets. Only accessible to staff and course leaders."""
    course = get_object_or_404(Course, pk=pk)
    assert isinstance(request.user, User)

    # Check if user is staff or a leader
    is_leader = (
        request.user.is_staff or course.leaders.filter(pk=request.user.pk).exists()
    )
    if not is_leader:
        messages.error(request, "You don't have permission to manage this course.")
        return redirect("courses:course_detail", pk=course.pk)

    # Create a formset for course meetings
    MeetingFormSet = modelformset_factory(
        CourseMeeting,
        form=CourseMeetingForm,
        extra=3,  # Number of empty forms to display
        can_delete=True,
    )

    if request.method == "POST":
        formset = MeetingFormSet(
            request.POST,
            queryset=CourseMeeting.objects.filter(course=course).order_by("start_time"),
        )
        if formset.is_valid():
            instances = formset.save(commit=False)
            # Set the course for new instances
            for instance in instances:
                instance.course = course
                instance.save()
            # Handle deletions
            for obj in formset.deleted_objects:
                obj.delete()
            messages.success(request, "Meetings updated successfully!")
            return redirect("courses:manage_meetings", pk=course.pk)
    else:
        formset = MeetingFormSet(
            queryset=CourseMeeting.objects.filter(course=course).order_by("start_time")
        )

    return render(
        request,
        "courses/manage_meetings.html",
        {"course": course, "formset": formset},
    )


class SortingHatView(UserPassesTestMixin, View):
    """Superuser-only view for bulk house assignment."""

    def test_func(self) -> bool:
        """Only superusers can access this view."""
        return self.request.user.is_superuser  # type: ignore[attr-defined]

    def get(self, request: HttpRequest) -> HttpResponse:
        """Display the sorting hat form."""
        form = SortingHatForm()
        return render(request, "courses/sorting_hat.html", {"form": form})

    def post(self, request: HttpRequest) -> HttpResponse:
        """Process bulk house assignment."""
        form = SortingHatForm(request.POST)
        if not form.is_valid():
            return render(request, "courses/sorting_hat.html", {"form": form})

        semester = form.cleaned_data["semester"]
        results = {
            "assigned": [],
            "not_found": [],
        }

        # Process each house
        house_fields = {
            "blob": Student.House.BLOB,
            "cat": Student.House.CAT,
            "owl": Student.House.OWL,
            "red_panda": Student.House.RED_PANDA,
            "bunny": Student.House.BUNNY,
        }

        for field_name, house_value in house_fields.items():
            airtable_names_text = form.cleaned_data.get(field_name, "")
            if not airtable_names_text:
                continue

            # Split by lines and strip whitespace
            airtable_names = [
                name.strip()
                for name in airtable_names_text.strip().split("\n")
                if name.strip()
            ]

            for airtable_name in airtable_names:
                try:
                    student = Student.objects.get(
                        airtable_name=airtable_name, semester=semester
                    )
                    student.house = house_value
                    student.save()
                    results["assigned"].append(
                        f"{airtable_name} → {house_value.label}"
                    )
                except Student.DoesNotExist:
                    results["not_found"].append(
                        f"{airtable_name} (not found in {semester})"
                    )

        return render(
            request,
            "courses/sorting_hat.html",
            {"form": form, "results": results},
        )
