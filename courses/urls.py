from django.urls import path

from courses import views

app_name = "courses"

urlpatterns = [
    path("", views.catalog_root, name="catalog_root"),
    path("all/", views.semester_list, name="semester_list"),
    path("my/", views.my_courses, name="my_courses"),
    path("my-clubs/", views.my_clubs, name="my_clubs"),
    path("past-clubs/", views.past_clubs, name="past_clubs"),
    path("upcoming/", views.upcoming, name="upcoming"),
    path(
        "bulk-create-students/", views.bulk_create_students, name="bulk_create_students"
    ),
    path("course/<int:pk>/", views.CourseDetailView.as_view(), name="course_detail"),
    path(
        "course/<int:pk>/edit/", views.CourseUpdateView.as_view(), name="course_update"
    ),
    path("course/<int:pk>/meetings/", views.manage_meetings, name="manage_meetings"),
    path("club/<int:pk>/join/", views.join_club, name="join_club"),
    path("club/<int:pk>/drop/", views.drop_club, name="drop_club"),
    path("<slug:slug>/", views.course_list, name="course_list"),
]
