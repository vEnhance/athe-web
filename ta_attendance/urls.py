from django.urls import path

from . import views

app_name = "ta_attendance"

urlpatterns = [
    path("", views.my_attendance, name="my_attendance"),
    path("all/", views.all_attendance, name="all_attendance"),
]
