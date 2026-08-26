from datetime import timedelta
from typing import Any, NamedTuple

from django import forms
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import Sum
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView, UpdateView

from courses.models import Course, CourseMeeting, Semester, Student
from housepoints.models import Award
from yearbook.models import YearbookEntry

from .models import ApplyPSet, StaffPhotoListing


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

    return render(request, "home/dashboard.html", context)


def index(request: HttpRequest) -> HttpResponse:
    """The site root: a dashboard once logged in, the public splash page if not."""
    if request.user.is_authenticated:
        return dashboard(request)
    return render(request, "home/index.html")


class UserProfileForm(forms.ModelForm):
    """Form for updating user profile information."""

    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]


class ProfileSettingsView(LoginRequiredMixin, View):
    """View for users to update their profile settings."""

    template_name = "home/profile_settings.html"

    def get(self, request: HttpRequest) -> HttpResponse:
        """Display the profile settings forms."""
        profile_form = UserProfileForm(instance=request.user)
        password_form = PasswordChangeForm(request.user)
        context = {
            "profile_form": profile_form,
            "password_form": password_form,
        }
        return render(request, self.template_name, context)

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle form submissions for profile or password updates."""
        if "update_profile" in request.POST:
            profile_form = UserProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Your profile has been updated successfully.")
                return redirect("home:profile_settings")
            password_form = PasswordChangeForm(request.user)
        elif "change_password" in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(
                    request, "Your password has been changed successfully."
                )
                return redirect("home:profile_settings")
            profile_form = UserProfileForm(instance=request.user)
        else:
            profile_form = UserProfileForm(instance=request.user)
            password_form = PasswordChangeForm(request.user)

        context = {
            "profile_form": profile_form,
            "password_form": password_form,
        }
        return render(request, self.template_name, context)


class StaffListingView(TemplateView):
    """Base page listing staff, one context entry per category shown."""

    categories: tuple[StaffPhotoListing.Category, ...] = ()

    def get_context_data(self, **kwargs):  # type: ignore
        """Add staff listings grouped by category."""
        context = super().get_context_data(**kwargs)
        for category in self.categories:
            context[category.value] = StaffPhotoListing.objects.filter(
                category=category
            )
        return context


class StaffView(StaffListingView):
    """Current staff page."""

    template_name = "home/staff.html"
    categories = (
        StaffPhotoListing.Category.BOARD,
        StaffPhotoListing.Category.INSTRUCTOR,
        StaffPhotoListing.Category.TA,
    )


class PastStaffView(StaffListingView):
    """Past staff page."""

    template_name = "home/past_staff.html"
    categories = (StaffPhotoListing.Category.XSTAFF,)


class StaffDetailView(DetailView):
    """Staff member detail page."""

    model = StaffPhotoListing
    template_name = "home/staff_detail.html"
    context_object_name = "staff_member"

    def get_context_data(self, **kwargs):  # type: ignore
        """Add courses taught by this staff member."""
        context = super().get_context_data(**kwargs)
        context["courses_taught"] = self.object.courses.select_related("semester").all()
        return context


class StaffPhotoUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for staff members to update their own listing."""

    model = StaffPhotoListing
    fields = [
        "display_name",
        "biography",
        "photo",
        "website",
        "email",
        "instagram_username",
        "discord_username",
        "github_username",
    ]
    template_name = "home/staff_edit.html"
    success_url = reverse_lazy("home:staff")

    def test_func(self) -> bool:
        """Only allow the user to edit their own listing."""
        obj = self.get_object()
        return obj.user == self.request.user

    def get_object(self, queryset=None):  # type: ignore
        """Get the staff listing for the current user."""
        return get_object_or_404(StaffPhotoListing, user=self.request.user)


class ApplyView(TemplateView):
    """Apply to be a student page."""

    template_name = "home/apply.html"

    def get_context_data(self, **kwargs):  # type: ignore
        """Add active psets or closed message."""
        context = super().get_context_data(**kwargs)

        active_psets = ApplyPSet.objects.filter(status=ApplyPSet.Status.ACTIVE)

        if active_psets.exists():
            context["active_psets"] = active_psets
        else:
            context["most_recent_pset"] = ApplyPSet.objects.filter(
                status=ApplyPSet.Status.COMPLETED
            ).first()

        return context


class PastPsetsView(ListView):
    """Past Problem Sets listing page."""

    model = ApplyPSet
    template_name = "home/past_psets.html"
    context_object_name = "psets"

    def get_queryset(self):  # type: ignore
        """Return only completed problem sets in reverse chronological order."""
        return ApplyPSet.objects.filter(status=ApplyPSet.Status.COMPLETED).order_by(
            "-deadline"
        )


class ManualView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Manual page for superusers."""

    def test_func(self) -> bool:
        return isinstance(self.request.user, User) and self.request.user.is_superuser

    template_name = "home/manual.html"
