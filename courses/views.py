from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from courses.models import Semester, Course


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
