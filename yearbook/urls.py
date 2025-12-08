from django.urls import path

from . import views

app_name = "yearbook"

urlpatterns = [
    path(
        "",
        views.YearbookIndexView.as_view(),
        name="index",
    ),
    path(
        "semesters/",
        views.SemesterListView.as_view(),
        name="semester_list",
    ),
    path(
        "<slug:slug>/",
        views.YearbookEntryListView.as_view(),
        name="entry_list",
    ),
    path(
        "entry/<int:pk>/",
        views.YearbookEntryDetailView.as_view(),
        name="entry_detail",
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
