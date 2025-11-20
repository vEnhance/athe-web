from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from django.views.generic import DetailView, TemplateView, UpdateView

from .models import StaffPhotoListing


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


class PastPsetsView(TemplateView):
    """Past Problem Sets / Application page."""

    template_name = "home/past_psets.html"


class LegalView(TemplateView):
    """Legal page."""

    template_name = "home/legal.html"
