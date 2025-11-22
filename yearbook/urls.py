from django.urls import path

from . import views

app_name = "yearbook"

urlpatterns = [
    path(
        "<slug:slug>/",
        views.SemesterYearbookListView.as_view(),
        name="semester_list",
    ),
    path(
        "create/<int:student_pk>/",
        views.YearbookEntryCreateView.as_view(),
        name="create",
    ),
    path(
        "edit/<int:pk>/",
        views.YearbookEntryUpdateView.as_view(),
        name="edit",
    ),
]
