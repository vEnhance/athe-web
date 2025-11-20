from django.urls import path

from .views import StaffInviteView

app_name = "reg"

urlpatterns = [
    path("invite/<uuid:invite_id>/", StaffInviteView.as_view(), name="invite"),
]
