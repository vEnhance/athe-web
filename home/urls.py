from django.urls import path
from django.views.generic import TemplateView
from django.views.generic import RedirectView

from home import views
from weblog.views import HistoryListView

app_name = "home"


def T(name: str):
    return TemplateView.as_view(template_name=name)


urlpatterns = [
    path("", T("home/index.html"), name="index"),
    path("about/", T("home/about.html"), name="about"),
    path("donors/", T("home/donors.html"), name="donors"),
    path("virtual-program/", T("home/virtual_program.html"), name="virtual_program"),
    path("scholarships/", T("home/scholarships.html"), name="scholarships"),
    path("legal/", T("home/legal.html"), name="legal"),
    path(
        "profile/settings/",
        views.ProfileSettingsView.as_view(),
        name="profile_settings",
    ),
    path("staff/", views.StaffView.as_view(), name="staff"),
    path("staff/past", views.PastStaffView.as_view(), name="past_staff"),
    path("staff/edit/", views.StaffPhotoUpdateView.as_view(), name="staff_edit"),
    path("staff/<slug:slug>/", views.StaffDetailView.as_view(), name="staff_detail"),
    path("history/", HistoryListView.as_view(), name="history"),
    path("apply/", views.ApplyView.as_view(), name="apply"),
    path("past-psets/", views.PastPsetsView.as_view(), name="past_psets"),
    path("admin-manual/", views.ManualView.as_view(), name="manual"),
    path(
        "alumapp/",
        RedirectView.as_view(
            url="https://airtable.com/app26vQ9wjACgHpTh/shrgVj1IXP9Uv7jyz",
            permanent=False,
        ),
        name="alumapp",
    ),
]
