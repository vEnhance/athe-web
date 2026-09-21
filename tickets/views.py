from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import User
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponseBase
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from courses.models import Course, Semester, Student

from .forms import TicketForm, TicketReviewForm
from .models import Ticket

DM_FILTER = "dm"


def current_student(user: User) -> Student | None:
    """This user's student row in the semester they are allowed to know about."""
    semester = Semester.objects.visible_to(user).unfinished().first()
    if semester is None:
        return None
    return Student.objects.filter(user=user, semester=semester).first()


class StaffOnlyMixin(LoginRequiredMixin, UserPassesTestMixin):
    """The gate on both review pages."""

    request: HttpRequest

    def test_func(self) -> bool:
        return self.request.user.is_staff  # type: ignore[union-attr]

    def handle_no_permission(self) -> HttpResponseBase:
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(self.request, "You must be staff to review questions.")
        return redirect("index")


class TicketCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Ticket
    form_class = TicketForm
    template_name = "tickets/ticket_form.html"

    def test_func(self) -> bool:
        assert isinstance(self.request.user, User)
        return current_student(self.request.user) is not None

    def handle_no_permission(self) -> HttpResponseBase:
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()
        messages.error(
            self.request,
            "Only students enrolled in the current semester can submit questions.",
        )
        return redirect("index")

    def form_valid(self, form: TicketForm) -> HttpResponseBase:
        assert isinstance(self.request.user, User)
        student = current_student(self.request.user)
        assert student is not None
        form.instance.student = student
        response = super().form_valid(form)
        meeting = form.instance.meeting
        if meeting is None:
            messages.success(
                self.request,
                "Your question has been submitted. Staff will answer it by Discord DM.",
            )
        else:
            when = timezone.localtime(meeting.start_time)
            messages.success(
                self.request,
                f"You've selected to have your question answered via "
                f"{meeting.course.name} on {when:%A %B %-d, %-I:%M %p %Z}. "
                f"Remember to join the office-hours-voice-1 Discord voice channel!",
            )
        return response

    def get_success_url(self) -> str:
        return reverse("tickets:ticket_list")


class TicketListView(LoginRequiredMixin, ListView):
    """A student's own questions, newest first."""

    model = Ticket
    template_name = "tickets/ticket_list.html"
    context_object_name = "tickets"

    def get_queryset(self) -> QuerySet[Ticket]:
        return (
            Ticket.objects.filter(student__user=self.request.user)
            .select_related("meeting", "meeting__course")
            .order_by("-created_at")
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        assert isinstance(self.request.user, User)
        context = super().get_context_data(**kwargs)
        context["can_submit"] = current_student(self.request.user) is not None
        return context


class StaffTicketListView(StaffOnlyMixin, ListView):
    """The staff queue: every question, oldest first."""

    model = Ticket
    template_name = "tickets/ticket_review_list.html"
    context_object_name = "tickets"

    def get_queryset(self) -> QuerySet[Ticket]:
        tickets = Ticket.objects.for_review()
        chosen = self.request.GET.get("session", "")
        if chosen == DM_FILTER:
            return tickets.filter(meeting__isnull=True)
        if chosen.isdigit():
            return tickets.filter(meeting__course=int(chosen))
        return tickets

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["sessions"] = Course.objects.filter(is_office_hours=True).unfinished()
        context["chosen_session"] = self.request.GET.get("session", "")
        context["dm_filter"] = DM_FILTER
        context["followed"] = set(
            Ticket.objects.followed_by(self.request.user).values_list("pk", flat=True)
        )
        return context


class StaffTicketUpdateView(StaffOnlyMixin, UpdateView):
    model = Ticket
    queryset = Ticket.objects.select_related("student__user", "student__registration")
    form_class = TicketReviewForm
    template_name = "tickets/ticket_review_form.html"
    context_object_name = "ticket"

    def form_valid(self, form: TicketReviewForm) -> HttpResponseBase:
        assert isinstance(self.request.user, User)
        # Only stamp who closed a ticket when this save is what closed it, so
        # editing the notes on a resolved ticket does not rewrite its history.
        if not form.cleaned_data["resolved"]:
            form.instance.unresolve()
        elif not form.instance.is_resolved:
            form.instance.resolve(self.request.user)
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse("tickets:review_list")
