from django.urls import path

from weblog import views

app_name = "weblog"

urlpatterns = [
    # Blog post URLs
    path("", views.BlogPostListView.as_view(), name="blog_list"),
    path("my/", views.BlogPostLandingView.as_view(), name="blog_landing"),
    path("create/", views.BlogPostCreateView.as_view(), name="blog_create"),
    path("<slug:slug>/", views.BlogPostDetailView.as_view(), name="blog_detail"),
    path("<slug:slug>/edit/", views.BlogPostUpdateView.as_view(), name="blog_update"),
]

# Confusingly, views.HistoryListView is actually under the home app
# because we don't want to preface it with the blog url
