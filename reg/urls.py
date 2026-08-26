from django.urls import path

from . import views

app_name = "reg"

urlpatterns = [
    path(
        "add-staff/<uuid:invite_id>/",
        views.StaffInviteView.as_view(),
        name="add-staff",
    ),
    path(
        "add-student/<uuid:invite_id>/",
        views.StudentInviteView.as_view(),
        name="add-student",
    ),
    path(
        "add-student/<uuid:invite_id>/<slug:step>/",
        views.StudentRegistrationStepView.as_view(),
        name="student-step",
    ),
    path("responses/<slug:slug>.json", views.student_responses, name="responses"),
    path("assignments/", views.upload_assignments, name="upload-assignments"),
]
