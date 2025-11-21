from django.urls import path

from .views import StaffInviteView, StudentInviteView

app_name = "reg"

urlpatterns = [
    path("add-staff/<uuid:invite_id>/", StaffInviteView.as_view(), name="add-staff"),
    path(
        "add-student/<uuid:invite_id>/",
        StudentInviteView.as_view(),
        name="add-student",
    ),
]
