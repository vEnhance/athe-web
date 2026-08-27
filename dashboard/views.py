"""The logged-in landing page.

This app owns no models. It reads from the apps that do (courses, housepoints,
yearbook) and assembles a single page out of them, which keeps that fan-out out
of ``home`` -- ``courses.models`` imports ``home.models``, so a dashboard living
in ``home`` put the two apps on both ends of the same arrow.
"""

from datetime import date, timedelta
from typing import Any, NamedTuple

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from courses.models import Course, CourseMeeting, GlobalEvent, Semester, Student
from housepoints.models import Award
from reg import wizard
from reg.models import StudentInviteLink, StudentRegistration
from yearbook.models import YearbookEntry


class DashboardCourse(NamedTuple):
    """A course shown on the dashboard, paired with its next meeting (if any)."""

    course: Course
    next_meeting: CourseMeeting | None


class DashboardNotice(NamedTuple):
    """The banner above the class lists, naming what a student is waiting on."""

    #: Which message to print; the branches live in components/notice.html.
    kind: str
    semester: Semester
    #: Where to finish the questionnaire. Only set when kind is "registration".
    url: str = ""


def _student_notice(student: Student, today: date) -> DashboardNotice | None:
    """What this student is still waiting on for their semester, if anything."""
    registration = StudentRegistration.objects.filter(student=student).first()
    if not wizard.is_complete(registration):
        # The questionnaire is only reachable off an invite link, so without a
        # live one there is nowhere to send them and nothing worth saying.
        invite = (
            StudentInviteLink.objects.filter(
                semester=student.semester, expiration_date__gt=timezone.now()
            )
            .order_by("-expiration_date")
            .first()
        )
        if invite is None:
            return None
        return DashboardNotice(
            "registration", student.semester, invite.get_absolute_url()
        )

    # Classes land in a lump when the matching is computed, which happens after
    # registration closes but before the semester opens. An empty dashboard is
    # only worth explaining in that window; once the semester has started, the
    # course lists say "not enrolled in any classes" for themselves.
    if student.semester.start_date <= today:
        return None
    if Course.objects.filter(students=student, is_club=False).exists():
        return None
    return DashboardNotice("assignments", student.semester)


def _dashboard_notice(user: User, current: Semester | None) -> DashboardNotice | None:
    """The banner above the class lists: why the dashboard looks so empty.

    A student can be stuck in three different places -- a questionnaire they
    never finished, a matching that has not been run yet, or no registration at
    all -- and every one of them leaves the same blank page behind, so name the
    one they are in rather than let them worry. The order matters: the two that
    are about this student's own paperwork come first, since they are the only
    ones they can do anything about.

    Whether the semester has opened is not one of these. The current semester
    is the current semester before its start date as much as after, so that is
    a plain fact stated elsewhere on the page, not a state to be stuck in.

    ``current`` is the semester as this user sees it, so a semester still kept
    back from students is not one they get told about. Staff have no Student
    row by design, so none of this is theirs.
    """
    if user.is_staff:
        return None

    today = timezone.localdate()
    students = list(
        Student.objects.filter(user=user, semester__end_date__gte=today)
        .select_related("semester")
        .order_by("semester__start_date")
    )
    for student in students:
        if (notice := _student_notice(student, today)) is not None:
            return notice
    if students or current is None:
        return None

    # Nothing to be waiting on, so point them at the semester they have missed.
    return DashboardNotice("not_enrolled", current)


def _dashboard_courses(
    user: User,
) -> tuple[list[DashboardCourse], list[DashboardCourse]]:
    """The user's current classes and clubs, each with the next meeting on it."""
    courses = list(
        Course.objects.for_user(user)
        .unfinished()
        .select_related("semester")
        # A semester about to open sorts after the one still running, on the
        # chance someone is enrolled in both across the turn of the year.
        .order_by("semester__start_date", "name")
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
    # The semester this user is allowed to know about: a semester held back
    # from students is not the current one as far as they are concerned.
    current = Semester.objects.visible_to(request.user).unfinished().first()
    student = (
        None
        if current is None
        else Student.objects.filter(user=request.user, semester=current)
        .select_related("semester")
        .first()
    )

    # The yearbook stays with the student's latest semester rather than the
    # running one, so alumnae keep reaching their old entry and an incoming
    # student can write theirs before the semester opens.
    yearbook_student = (
        Student.objects.filter(user=request.user)
        .select_related("semester")
        .order_by("-semester__start_date")
        .first()
    )

    events = GlobalEvent.objects.current_for(request.user)
    context: dict[str, Any] = {
        "dash_classes": classes,
        "dash_clubs": clubs,
        "notice": _dashboard_notice(request.user, current),
        "has_current_semester": current is not None,
        # Stated plainly rather than folded into the banner: a semester that
        # has not opened yet is still the one everything else is about.
        "upcoming_semester": (
            current
            if current is not None and current.start_date > timezone.localdate()
            else None
        ),
        "global_event_count": events.count(),
        "next_global_event": events.filter(start_time__gte=timezone.now()).first(),
        "yearbook_student": yearbook_student,
        # The two section headings are links into a semester of the user's own;
        # anyone who has never enrolled gets the default view instead.
        "house_url": reverse("housepoints:leaderboard"),
        "yearbook_url": reverse("yearbook:index"),
    }
    if student is not None:
        context |= _dashboard_house(student)
        context["house_url"] = reverse(
            "housepoints:leaderboard_semester", kwargs={"slug": student.semester.slug}
        )
    if yearbook_student is not None:
        semester = yearbook_student.semester
        context["yearbook_url"] = reverse(
            "yearbook:entry_list", kwargs={"slug": semester.slug}
        )
        context["yearbook_entry"] = YearbookEntry.objects.filter(
            student=yearbook_student
        ).first()
        context["yearbook_open"] = timezone.localdate() <= semester.end_date

    return render(request, "dashboard/index.html", context)
