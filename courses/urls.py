from django.urls import path

from courses import views

app_name = "courses"

urlpatterns = [
    path("", views.catalog_root, name="catalog_root"),
    path("all/", views.semester_list, name="semester_list"),
    path("my/", views.my_courses, name="my_courses"),
    path("course/<int:pk>/", views.CourseDetailView.as_view(), name="course_detail"),
    path("<slug:slug>/", views.course_list, name="course_list"),
]
