import calendar
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Any

import icalendar
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef
from django.forms import modelformset_factory
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, UpdateView

from atheweb.decorators import staff_required, superuser_required
from courses.forms import (
    BulkStudentCreationForm,
    CourseMeetingForm,
    CourseUpdateForm,
)
from courses.models import (
    CalendarToken,
    Course,
    CourseMeeting,
    GlobalEvent,
    Semester,
    Student,
)
from home.models import StaffPhotoListing


def catalog_root(request: HttpRequest) -> HttpResponse:
    """Show the most recent semester as the main catalog landing page."""
    latest_semester = Semester.objects.visible_to(request.user).first()
    if latest_semester:
        return redirect("courses:course_list", slug=latest_semester.slug)
    return render(request, "courses/semester_list.html", {"semesters": []})


def semester_list(request: HttpRequest) -> HttpResponse:
    """Show all semesters in chronological order."""
    semesters = Semester.objects.visible_to(request.user)
    return render(request, "courses/semester_list.html", {"semesters": semesters})


def course_list(request: HttpRequest, slug: str) -> HttpResponse:
    """Show courses for a specific semester with previous/next navigation."""
    visible = Semester.objects.visible_to(request.user)
    semester = get_object_or_404(visible, slug=slug)

    # Filter to only show classes (not clubs)
    courses = Course.objects.filter(semester=semester, is_club=False).select_related(
        "instructor"
    )

    prev_semester = visible.filter(start_date__lt=semester.start_date).first()
    next_semester = (
        visible.filter(start_date__gt=semester.start_date)
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
    assert isinstance(request.user, User)

    enrolled_courses = (
        Course.objects.for_user(request.user)
        .filter(is_club=False)
        .select_related("semester", "instructor")
    )

    return render(
        request,
        "courses/my_courses.html",
        {"enrolled_courses": enrolled_courses},
    )


@login_required
def my_clubs(request: HttpRequest) -> HttpResponse:
    """Show the current semester's clubs, split by enrollment. Includes led clubs."""
    assert isinstance(request.user, User)

    current = Semester.current()
    current_clubs = (
        Course.objects.none()
        if current is None
        else Course.objects.filter(is_club=True, semester=current)
    )

    if request.user.is_staff:
        # Staff follow clubs instead of joining them: enrolment is a Student
        # row, and some staff keep a dummy one for testing, so the two must not
        # be read as the same thing. Following is also not a claim to run a
        # club -- it is just what someone wants on their own calendar.
        enrolled_clubs = current_clubs.followed_by(request.user)
        available_clubs = current_clubs.exclude(pk__in=enrolled_clubs)
        has_current_semester = True
    else:
        enrolled_clubs = current_clubs.for_user(request.user)
        # Students may only join clubs in a semester they are enrolled in.
        available_clubs = current_clubs.filter(
            semester__students__user=request.user
        ).exclude(pk__in=enrolled_clubs)
        has_current_semester = current is not None and (
            enrolled_clubs.exists()
            or Student.objects.filter(user=request.user, semester=current).exists()
        )

    return render(
        request,
        "courses/my_clubs.html",
        {
            "enrolled_clubs": enrolled_clubs.select_related("semester", "instructor"),
            "available_clubs": available_clubs.select_related("semester", "instructor"),
            "has_current_semester": has_current_semester,
            "is_staff_view": request.user.is_staff,
            "enrolled_heading": "Clubs You Follow"
            if request.user.is_staff
            else "Enrolled Clubs",
        },
    )


@login_required
def past_clubs(request: HttpRequest) -> HttpResponse:
    """Show all clubs from visible past semesters (readonly)."""
    today = timezone.now().date()

    # Get all clubs from visible semesters that have ended
    past_clubs_queryset = Course.objects.filter(
        is_club=True,
        semester__end_date__lt=today,
        semester__visible=True,
    ).select_related("semester", "instructor")

    # Convert to list and sort by semester (most recent first), then by course name
    past_clubs_list = sorted(
        past_clubs_queryset,
        key=lambda c: (-c.semester.start_date.toordinal(), c.name),
    )

    return render(
        request,
        "courses/past_clubs.html",
        {"past_clubs": past_clubs_list},
    )


def _staff_listing(request: HttpRequest) -> StaffPhotoListing | None:
    """The current staff listing for this user, if they have one."""
    return StaffPhotoListing.objects.active().filter(user=request.user).first()


@login_required
@require_POST
def subscribe_course(request: HttpRequest, pk: int) -> HttpResponse:
    """Put a course on this staff member's own pages.

    Deliberately nothing to do with joining: enrolment means a Student row,
    which some staff keep a dummy of for testing, and following a club says
    nothing about who runs or may edit it.
    """
    course = get_object_or_404(Course, pk=pk)
    listing = _staff_listing(request)
    if listing is None:
        messages.error(request, "Only current staff can follow a course.")
    else:
        course.subscribed_staff.add(listing)
        messages.success(request, f"{course.name} is now on your calendar.")
    return _back_to(course)


@login_required
@require_POST
def unsubscribe_course(request: HttpRequest, pk: int) -> HttpResponse:
    """Take a course back off this staff member's own pages."""
    course = get_object_or_404(Course, pk=pk)
    listing = _staff_listing(request)
    if listing is not None:
        course.subscribed_staff.remove(listing)
    messages.success(request, f"{course.name} is no longer on your calendar.")
    return _back_to(course)


def _back_to(course: Course) -> HttpResponse:
    """Where join, drop and the subscribe pair all send someone afterwards."""
    if course.is_club:
        return redirect("courses:my_clubs")
    return redirect("courses:course_detail", pk=course.pk)


@login_required
@require_POST
def join_club(request: HttpRequest, pk: int) -> HttpResponse:
    """Join a club if the user has student access to that semester."""
    club = get_object_or_404(Course, pk=pk, is_club=True)

    if club.semester != Semester.current():
        messages.error(request, "This club is not in the current semester.")
        return redirect("courses:my_clubs")

    # Get student record for this semester
    try:
        student = Student.objects.get(user=request.user, semester=club.semester)
    except Student.DoesNotExist:
        messages.error(request, "You are not a student in this semester.")
        return redirect("courses:my_clubs")

    # Check if already enrolled
    if club.students.filter(pk=student.pk).exists():
        messages.info(request, f"You are already enrolled in {club.name}.")
    else:
        club.students.add(student)
        messages.success(request, f"Successfully joined {club.name}!")

    return redirect("courses:my_clubs")


@login_required
@require_POST
def drop_club(request: HttpRequest, pk: int) -> HttpResponse:
    """Drop a club, as long as it is in the current semester."""
    club = get_object_or_404(Course, pk=pk, is_club=True)

    if club.semester != Semester.current():
        messages.error(request, "This club is not in the current semester.")
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


@staff_required(
    message="You don't have permission to view the staff schedule.",
    redirect_to="courses:catalog_root",
)
def staff_schedule(request: HttpRequest, slug: str | None = None) -> HttpResponse:
    """Staff-only master schedule: all course meetings for a semester.

    If no slug is given, defaults to the current semester.
    """
    all_semesters = list(Semester.objects.order_by("-start_date"))

    if slug is not None:
        semester = get_object_or_404(Semester, slug=slug)
    else:
        current = Semester.current()
        if current is None:
            return render(
                request,
                "courses/staff_schedule.html",
                {
                    "error": "There is no current semester to show.",
                    "all_semesters": all_semesters,
                },
            )
        semester = current

    sort = request.GET.get("sort", "course")

    base_qs = CourseMeeting.objects.filter(course__semester=semester).select_related(
        "course"
    )
    if sort == "course":
        base_qs = base_qs.order_by("course__name", "start_time")
    else:
        base_qs = base_qs.order_by("start_time", "course__name")

    courses_qs = Course.objects.filter(semester=semester).order_by("name")
    courses_with_meetings = set(
        CourseMeeting.objects.filter(course__semester=semester).values_list(
            "course_id", flat=True
        )
    )

    return render(
        request,
        "courses/staff_schedule.html",
        {
            "semester": semester,
            "all_semesters": all_semesters,
            "class_meetings": list(base_qs.filter(course__is_club=False)),
            "club_meetings": list(base_qs.filter(course__is_club=True)),
            "classes_without_meetings": list(
                courses_qs.filter(is_club=False).exclude(pk__in=courses_with_meetings)
            ),
            "clubs_without_meetings": list(
                courses_qs.filter(is_club=True).exclude(pk__in=courses_with_meetings)
            ),
            "sort": sort,
        },
    )


@login_required
def upcoming(request: HttpRequest) -> HttpResponse:
    """Show upcoming meetings and events for courses/clubs the user is in or leads."""
    assert isinstance(request.user, User)
    now = timezone.now()

    upcoming_meetings = (
        CourseMeeting.objects.filter(
            course__in=Course.objects.for_user(request.user), start_time__gte=now
        )
        .select_related("course", "course__semester")
        .order_by("start_time")
    )
    upcoming_events = GlobalEvent.objects.visible_to(request.user).filter(
        start_time__gte=now
    )

    return render(
        request,
        "courses/upcoming.html",
        {
            "upcoming_meetings": upcoming_meetings,
            "upcoming_events": upcoming_events,
        },
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

        # Reading a course and editing it are different questions: any staff
        # member may look at any course, while ``is_managed_by`` is narrower.
        if self.request.user.is_staff or course.is_managed_by(self.request.user):
            return True

        # Non-staff users cannot access courses in invisible semesters
        if not course.semester.visible:
            return False

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
        context["members"] = self.object.students.select_related("user")

        context["is_leader"] = self.object.is_managed_by(self.request.user)

        # Staff follow a course instead of joining it, on any course and for
        # as long as it exists: it only ever affects their own pages.
        context["can_subscribe"] = _staff_listing(self.request) is not None
        context["is_subscribed"] = self.object.is_followed_by(self.request.user)

        # For clubs in active semesters, check if user can join/drop
        if self.object.is_club and self.object.semester == Semester.current():
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
    Only accessible to superusers, the instructor, or staff on an active club.
    """

    model = Course
    form_class = CourseUpdateForm
    template_name = "courses/course_update.html"
    context_object_name = "course"

    def test_func(self) -> bool:
        """Check whether this user may edit the course."""
        return self.get_object().is_managed_by(self.request.user)

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
    """Manage meetings for a course using inline formsets, for whoever runs it."""
    course = get_object_or_404(Course, pk=pk)
    if not course.is_managed_by(request.user):
        messages.error(request, "You don't have permission to manage this course.")
        return redirect("courses:course_detail", pk=course.pk)

    # Create a formset for course meetings
    MeetingFormSet = modelformset_factory(
        CourseMeeting,
        form=CourseMeetingForm,
        extra=0,  # JavaScript handles adding new forms dynamically
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


@superuser_required()
def bulk_create_students(request: HttpRequest) -> HttpResponse:
    """Bulk create students for a semester. Only accessible to superusers.

    Names only: the students themselves supply everything else through the
    registration link, and their classes and houses arrive later from the
    computed matching.
    """
    form = BulkStudentCreationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        semester = form.cleaned_data["semester"]
        names = form.cleaned_data["students"]

        Student.objects.bulk_create(
            [
                Student(airtable_name=airtable_name, semester=semester)
                for airtable_name in names
            ],
            ignore_conflicts=True,
        )

        created = Student.objects.filter(
            airtable_name__in=names, semester=semester
        ).count()
        messages.success(
            request,
            f"Successfully processed {len(names)} names; "
            f"{created} students now exist for {semester}.",
        )
        return redirect("courses:bulk_create_students")

    return render(request, "courses/bulk_create_students.html", {"form": form})


def _requested_month(request: HttpRequest, today: date) -> tuple[int, int]:
    """Read ?year=&month= from the query string, falling back to this month."""
    try:
        year = int(request.GET["year"])
        month = int(request.GET["month"])
    except KeyError, ValueError:
        return today.year, today.month
    if not 1 <= month <= 12:
        return today.year, today.month
    return year, month


def _calendar_events(
    request: HttpRequest, start: datetime, end: datetime
) -> list[dict[str, Any]]:
    """Every event to draw on the calendar between two instants, with categories."""
    events: list[dict[str, Any]] = [
        {
            "title": event.title,
            "start_time": event.start_time,
            "category": "global",
            "url": event.get_absolute_url(),
            "semester": event.semester.name,
        }
        # GlobalEvents: everyone sees all visible semesters
        for event in GlobalEvent.objects.filter(
            start_time__range=(start, end), semester__visible=True
        ).select_related("semester")
    ]

    # CourseMeetings: fetch all in range for visible semesters, annotated with
    # is_mine (enrolled as a student, or following it as staff). Non-enrolled
    # classes are skipped; clubs are shown either way.
    is_enrolled = Exists(
        Course.students.through.objects.filter(
            course_id=OuterRef("course_id"),
            student__user=request.user,
        )
    )
    is_following = Exists(
        Course.objects.followed_by(request.user).filter(pk=OuterRef("course_id"))
    )
    meetings = (
        CourseMeeting.objects.filter(
            start_time__range=(start, end),
            course__semester__visible=True,
        )
        .select_related("course", "course__semester")
        .annotate(is_mine=is_enrolled | is_following)
    )

    for meeting in meetings:
        is_club: bool = meeting.course.is_club
        is_mine: bool = meeting.is_mine  # type: ignore[attr-defined]
        if not is_club and not is_mine:
            continue
        if is_mine:
            category = "enrolled_club" if is_club else "enrolled_class"
        else:
            category = "other_club"
        events.append(
            {
                "title": meeting.course.name
                + (f": {meeting.title}" if meeting.title else ""),
                "start_time": meeting.start_time,
                "category": category,
                "url": meeting.course.get_absolute_url(),
                "semester": meeting.course.semester.name,
            }
        )

    return events


@login_required
def calendar_view(request: HttpRequest) -> HttpResponse:
    """Monthly calendar of every event the user can see."""
    assert isinstance(request.user, User)

    today = timezone.now().date()
    display_year, display_month = _requested_month(request, today)

    # Sunday is the first day of the week (6 in Python's calendar module)
    month_days = calendar.Calendar(firstweekday=6).monthdatescalendar(
        display_year, display_month
    )

    # The grid spills past the month, so fetch events for its full extent
    tz = timezone.get_current_timezone()
    range_start = timezone.make_aware(datetime.combine(month_days[0][0], time.min), tz)
    range_end = timezone.make_aware(datetime.combine(month_days[-1][-1], time.max), tz)

    events_by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for event in _calendar_events(request, range_start, range_end):
        events_by_day[timezone.localtime(event["start_time"]).date()].append(event)
    for day_events in events_by_day.values():
        day_events.sort(key=lambda e: e["start_time"])

    weeks_data = [
        [
            {
                "date": day,
                "is_current_month": day.month == display_month,
                "is_today": day == today,
                "events": events_by_day[day],
            }
            for day in week
        ]
        for week in month_days
    ]

    # Any month is at most 31 days, so +32 always lands inside the next one
    first_of_month = date(display_year, display_month, 1)
    prev_month_day = first_of_month - timedelta(days=1)
    next_month_day = (first_of_month + timedelta(days=32)).replace(day=1)

    cal_token, _ = CalendarToken.objects.get_or_create(user=request.user)
    feed_url = request.build_absolute_uri(
        reverse("courses:calendar-feed", kwargs={"token": cal_token.token})
    )

    return render(
        request,
        "courses/calendar.html",
        {
            "weeks_data": weeks_data,
            "display_year": display_year,
            "display_month": display_month,
            "month_name": calendar.month_name[display_month],
            "prev_year": prev_month_day.year,
            "prev_month": prev_month_day.month,
            "next_year": next_month_day.year,
            "next_month": next_month_day.month,
            "today": today,
            "timezone_name": timezone.get_current_timezone_name(),
            "feed_url": feed_url,
        },
    )


def calendar_feed(request: HttpRequest, token: str) -> HttpResponse:
    """
    Return a user-specific iCalendar (.ics) feed.

    The feed URL contains a secret token so no login session is required —
    Google Calendar (and other clients) can subscribe and auto-refresh it.
    """
    cal_token = get_object_or_404(CalendarToken, token=token)
    user = cal_token.user

    # Fetch events from 90 days in the past to 365 days in the future
    now = timezone.now()
    range_start = now - timedelta(days=90)
    range_end = now + timedelta(days=365)

    # Classes and clubs are treated identically in the feed
    enrolled_courses = Course.objects.for_user(user)

    cal = icalendar.Calendar()
    cal.add("prodid", "-//Athemath Calendar Feed//athemath.org//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")
    cal.add("x-wr-calname", "Athemath Calendar")
    cal.add("refresh-interval;value=duration", "PT12H")
    cal.add("x-published-ttl", "PT12H")

    domain = "athemath.org"

    global_events = GlobalEvent.objects.visible_to(user).filter(
        start_time__range=(range_start, range_end)
    )

    for event in global_events:
        vevent = icalendar.Event()
        vevent.add("uid", f"globalevent-{event.pk}@{domain}")
        vevent.add("summary", event.title)
        vevent.add("dtstart", event.start_time)
        vevent.add("dtend", event.start_time + timedelta(hours=1))
        if event.description:
            vevent.add("description", event.description)
        if event.link:
            vevent.add("url", event.link)
        vevent.add("dtstamp", now)
        cal.add_component(vevent)

    # CourseMeetings for enrolled courses
    meetings = CourseMeeting.objects.filter(
        course__in=enrolled_courses,
        start_time__range=(range_start, range_end),
    ).select_related("course", "course__semester")

    for meeting in meetings:
        vevent = icalendar.Event()
        vevent.add("uid", f"meeting-{meeting.pk}@{domain}")
        title = meeting.course.name + (f": {meeting.title}" if meeting.title else "")
        vevent.add("summary", title)
        vevent.add("dtstart", meeting.start_time)
        vevent.add("dtend", meeting.start_time + timedelta(hours=1))
        if meeting.course.zoom_meeting_link:
            vevent.add("url", meeting.course.zoom_meeting_link)
        vevent.add("dtstamp", now)
        cal.add_component(vevent)

    return HttpResponse(
        cal.to_ical(),
        content_type="text/calendar; charset=utf-8",
    )


@login_required
def global_events(request: HttpRequest) -> HttpResponse:
    """Every all-student event of this semester, past ones included."""
    assert isinstance(request.user, User)
    events = GlobalEvent.objects.current_for(request.user)
    return render(
        request,
        "courses/global_event_list.html",
        {"events": events, "now": timezone.now()},
    )


class GlobalEventDetailView(UserPassesTestMixin, DetailView):
    """
    Detail view for a global event.
    Only accessible to staff or students from the event's semester.
    """

    model = GlobalEvent
    template_name = "courses/global_event_detail.html"
    context_object_name = "event"

    def test_func(self) -> bool:
        """Check access permissions for global events."""
        if not self.request.user.is_authenticated:
            return False
        assert isinstance(self.request.user, User)

        event = self.get_object()

        # Staff users have access to everything
        if self.request.user.is_staff:
            return True

        # Non-staff users cannot access events in invisible semesters
        if not event.semester.visible:
            return False

        # Students from the event's semester can access
        return Student.objects.filter(
            user=self.request.user, semester=event.semester
        ).exists()
