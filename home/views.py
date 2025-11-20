from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views.generic import DetailView, ListView, TemplateView, UpdateView

from .models import ApplyPSet, StaffPhotoListing


def index(request: HttpRequest) -> HttpResponse:
    """Homepage view."""
    return render(request, "home/index.html")


class AboutView(TemplateView):
    """About Us page."""

    template_name = "home/about.html"


class StaffView(TemplateView):
    """Staff page."""

    template_name = "home/staff.html"

    def get_context_data(self, **kwargs):  # type: ignore
        """Add staff listings grouped by category."""
        context = super().get_context_data(**kwargs)
        context["board"] = StaffPhotoListing.objects.filter(category="board")
        context["instructor"] = StaffPhotoListing.objects.filter(category="instructor")
        context["ta"] = StaffPhotoListing.objects.filter(category="ta")
        return context


class PastStaffView(TemplateView):
    """Staff page."""

    template_name = "home/past_staff.html"

    def get_context_data(self, **kwargs):  # type: ignore
        """Add staff listings grouped by category."""
        context = super().get_context_data(**kwargs)
        context["xstaff"] = StaffPhotoListing.objects.filter(category="xstaff")
        return context


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
    fields = ["display_name", "biography", "photo"]
    template_name = "home/staff_edit.html"
    success_url = reverse_lazy("home:staff")

    def test_func(self) -> bool:
        """Only allow the user to edit their own listing."""
        obj = self.get_object()
        return obj.user == self.request.user

    def get_object(self, queryset=None):  # type: ignore
        """Get the staff listing for the current user."""
        return get_object_or_404(StaffPhotoListing, user=self.request.user)


class DonorsView(TemplateView):
    """Donors page."""

    template_name = "home/donors.html"


class HistoryView(TemplateView):
    """History page."""

    template_name = "home/history.html"


class VirtualProgramView(TemplateView):
    """Virtual Program page."""

    template_name = "home/virtual_program.html"


class ScholarshipsView(TemplateView):
    """Scholarships page."""

    template_name = "home/scholarships.html"


class ApplyView(TemplateView):
    """Apply to be a student page."""

    template_name = "home/apply.html"

    def get_context_data(self, **kwargs):  # type: ignore
        """Add active psets or closed message."""
        context = super().get_context_data(**kwargs)

        # Get all active problem sets
        active_psets = ApplyPSet.objects.filter(status="active")

        if active_psets.exists():
            # Show all active problem sets
            context["active_psets"] = active_psets
            context["show_active"] = True
        else:
            # Show closed message from most recent completed pset
            most_recent = ApplyPSet.objects.filter(status="completed").first()
            if most_recent:
                context["closed_message"] = most_recent.closed_message_rendered
                context["show_active"] = False
            else:
                # No psets at all
                context["show_active"] = False
                context["closed_message"] = None

        return context


class PastPsetsView(ListView):
    """Past Problem Sets listing page."""

    model = ApplyPSet
    template_name = "home/past_psets.html"
    context_object_name = "psets"

    def get_queryset(self):  # type: ignore
        """Return only completed problem sets in reverse chronological order."""
        return ApplyPSet.objects.filter(status="completed").order_by("-deadline")


class LegalView(TemplateView):
    """Legal page."""

    template_name = "home/legal.html"
