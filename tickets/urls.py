from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.TicketListView.as_view(), name="ticket_list"),
    path("submit/", views.TicketCreateView.as_view(), name="submit"),
    path("review/", views.StaffTicketListView.as_view(), name="review_list"),
    path(
        "review/<int:pk>/",
        views.StaffTicketUpdateView.as_view(),
        name="review_detail",
    ),
]
