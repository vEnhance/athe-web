from django.urls import path

from courses import views

urlpatterns = [
    path("", views.semester_list, name="semester_list"),
    path("<slug:slug>/", views.course_list, name="course_list"),
]
