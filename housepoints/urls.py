from django.urls import path

from housepoints import views

app_name = "housepoints"

urlpatterns = [
    path("", views.leaderboard, name="leaderboard"),
    path("awards/bulk/", views.BulkAwardView.as_view(), name="bulk_award"),
    path(
        "awards/attendance/",
        views.AttendanceBulkView.as_view(),
        name="attendance_bulk",
    ),
    path("awards/single/", views.SingleAwardView.as_view(), name="single_award"),
    path("awards/my/", views.my_awards, name="my_awards"),
    path("<slug:slug>/", views.leaderboard, name="leaderboard_semester"),
    path("<slug:slug>/<str:house>/", views.house_detail, name="house_detail"),
    path(
        "<slug:slug>/<str:house>/staff/",
        views.house_detail_staff,
        name="house_detail_staff",
    ),
]
