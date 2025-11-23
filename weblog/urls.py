from django.urls import path

from weblog import views

app_name = "weblog"

urlpatterns = [
    path("", views.HistoryListView.as_view(), name="history_list"),
    # Blog post URLs
    path("blog/", views.BlogPostListView.as_view(), name="blog_list"),
    path("blog/my/", views.BlogPostLandingView.as_view(), name="blog_landing"),
    path("blog/create/", views.BlogPostCreateView.as_view(), name="blog_create"),
    path("blog/<slug:slug>/", views.BlogPostDetailView.as_view(), name="blog_detail"),
    path(
        "blog/<slug:slug>/edit/", views.BlogPostUpdateView.as_view(), name="blog_update"
    ),
]
