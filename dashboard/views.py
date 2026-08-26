"""The logged-in landing page.

This app owns no models. It reads from the apps that do (courses, housepoints,
yearbook) and assembles a single page out of them, which keeps that fan-out out
of ``home`` -- ``courses.models`` imports ``home.models``, so a dashboard living
in ``home`` put the two apps on both ends of the same arrow.
"""

from datetime import timedelta
from typing import Any, NamedTuple

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseMeeting, Semester, Student
from housepoints.models import Award
from yearbook.models import YearbookEntry


class DashboardCourse(NamedTuple):
    """A course shown on the dashboard, paired with its next meeting (if any)."""

    course: Course
    next_meeting: CourseMeeting | None


def _dashboard_courses(
    user: User,
) -> tuple[list[DashboardCourse], list[DashboardCourse]]:
    """The user's active classes and clubs, each with the next meeting on it."""
    courses = list(
        Course.objects.for_user(user)
        .active()
        .select_related("semester")
        .order_by("name")
    )
    # A meeting counts as "next" until an hour after it starts, so a class does
    # not disappear from the dashboard while it is in session.
    horizon = timezone.now() - timedelta(hours=1)
    next_meetings: dict[int, CourseMeeting] = {}
    for meeting in (
        CourseMeeting.objects.filter(course__in=courses, start_time__gte=horizon)
        .select_related("course")
        .order_by("start_time")
    ):
        next_meetings.setdefault(meeting.course.pk, meeting)

    rows = [DashboardCourse(course, next_meetings.get(course.pk)) for course in courses]
    return (
        [row for row in rows if not row.course.is_club],
        [row for row in rows if row.course.is_club],
    )


def _dashboard_house(student: Student) -> dict[str, Any]:
    """House standing and personal point total for a student, if they have a house."""
    if not student.house:
        return {}
    semester = student.semester
    # The house total mirrors the leaderboard, which respects the freeze date;
    # the personal total mirrors My Awards, which does not.
    house_points = Award.objects.for_semester(semester).totals_by_house()[student.house]
    my_points = (
        Award.objects.for_semester(semester, respect_freeze=False)
        .filter(student=student)
        .aggregate(total=Sum("points"))["total"]
        or 0
    )
    return {
        "house_display": Student.House(student.house).label,
        "house_points": house_points,
        "my_points": my_points,
        "house_detail_url": reverse(
            "housepoints:house_detail",
            kwargs={"slug": semester.slug, "house": student.house},
        ),
    }


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Landing page for logged-in users: their classes, house, and staff tools."""
    assert isinstance(request.user, User)

    classes, clubs = _dashboard_courses(request.user)
    student = (
        Student.objects.filter(
            user=request.user, semester__in=Semester.objects.active()
        )
        .select_related("semester")
        .first()
    )

    context: dict[str, Any] = {
        "dash_classes": classes,
        "dash_clubs": clubs,
        "student": student,
        # The two section headings are links. Someone with a semester of their
        # own lands in it; everyone else (staff, alumnae) gets the default view.
        "house_url": reverse("housepoints:leaderboard"),
        "yearbook_url": reverse("yearbook:index"),
    }
    if student is not None:
        context |= _dashboard_house(student)
        context["house_url"] = reverse(
            "housepoints:leaderboard_semester", kwargs={"slug": student.semester.slug}
        )
        context["yearbook_url"] = reverse(
            "yearbook:entry_list", kwargs={"slug": student.semester.slug}
        )
        context["yearbook_entry"] = YearbookEntry.objects.filter(
            student=student
        ).first()
        context["yearbook_open"] = timezone.localdate() <= student.semester.end_date

    return render(request, "dashboard/index.html", context)
