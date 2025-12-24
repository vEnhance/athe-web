from django.urls import path
from django.views.generic import TemplateView


app_name = "misc"

urlpatterns = [
    path(
        "battle",
        TemplateView.as_view(template_name="misc/sp26game.html"),
        name="sp26game",
    )
]
