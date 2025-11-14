from django.urls import path

from home import views

app_name = "home"

urlpatterns = [
    path("", views.index, name="index"),
    path("about/", views.AboutView.as_view(), name="about"),
    path("staff/", views.StaffView.as_view(), name="staff"),
    path("staff/past", views.PastStaffView.as_view(), name="past_staff"),
    path("staff/edit/", views.StaffPhotoUpdateView.as_view(), name="staff_edit"),
    path("staff/<int:pk>/", views.StaffDetailView.as_view(), name="staff_detail"),
    path("donors/", views.DonorsView.as_view(), name="donors"),
    path("history/", views.HistoryView.as_view(), name="history"),
    path(
        "virtual-program/", views.VirtualProgramView.as_view(), name="virtual_program"
    ),
    path("scholarships/", views.ScholarshipsView.as_view(), name="scholarships"),
    path("past-psets/", views.PastPsetsView.as_view(), name="past_psets"),
    path("legal/", views.LegalView.as_view(), name="legal"),
]
