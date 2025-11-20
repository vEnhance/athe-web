from django.urls import path

from weblog import views

app_name = "weblog"

urlpatterns = [
    path("", views.HistoryListView.as_view(), name="history_list"),
]
