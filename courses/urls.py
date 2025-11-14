from django.urls import path

from courses import views

app_name = "courses"

urlpatterns = [
    path("", views.catalog_root, name="catalog_root"),
    path("all/", views.semester_list, name="semester_list"),
    path("<slug:slug>/", views.course_list, name="course_list"),
]
