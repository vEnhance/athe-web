from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.generic import TemplateView


def index(request: HttpRequest) -> HttpResponse:
    """Homepage view."""
    return render(request, "home/index.html")


class AboutView(TemplateView):
    """About Us page."""

    template_name = "home/about.html"


class StaffView(TemplateView):
    """Staff page."""

    template_name = "home/staff.html"


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
