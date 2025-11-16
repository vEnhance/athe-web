from django.urls import path

from housepoints import views

app_name = "housepoints"

urlpatterns = [
    path("", views.leaderboard, name="leaderboard"),
    path("<slug:slug>/", views.leaderboard, name="leaderboard_semester"),
    path("awards/bulk/", views.BulkAwardView.as_view(), name="bulk_award"),
    path("awards/my/", views.my_awards, name="my_awards"),
]
