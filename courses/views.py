from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView

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
    courses = Course.objects.filter(semester=semester).select_related("instructor")

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


class CourseDetailView(UserPassesTestMixin, DetailView):
    """
    Detail view for a course showing Google Classroom, Zoom links,
    and upcoming meetings. Accessible to staff or enrolled students.
    """

    model = Course
    template_name = "courses/course_detail.html"
    context_object_name = "course"

    def test_func(self) -> bool:
        """Check if user is staff or enrolled in this course."""
        if not self.request.user.is_authenticated:
            return False
        if self.request.user.is_staff:  # type: ignore[attr-defined]
            return True
        # Check if user is enrolled in this course
        course = self.get_object()
        return Student.objects.filter(
            user=self.request.user,
            enrolled_courses=course,
        ).exists()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get upcoming meetings (from now onwards)
        now = timezone.now()
        context["upcoming_meetings"] = CourseMeeting.objects.filter(
            course=self.object, start_time__gte=now
        ).order_by("start_time")
        return context
