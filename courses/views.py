from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from courses.models import Semester


def semester_list(request: HttpRequest) -> HttpResponse:
    semesters = Semester.objects.all()
    return render(request, "courses/semester_list.html", {"semesters": semesters})


def course_list(request: HttpRequest, slug: str) -> HttpResponse:
    semester = get_object_or_404(Semester, slug=slug)
    return render(request, "courses/course_list.html", {"semester": semester})
