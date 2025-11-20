from django.urls import path

from .views import StaffInviteView

app_name = "reg"

urlpatterns = [
    path("add-staff/<uuid:invite_id>/", StaffInviteView.as_view(), name="add-staff"),
]
