from typing import Any

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import QuerySet
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from home.models import StaffPhotoListing

from .models import BlogPost, HistoryEntry


class HistoryListView(ListView):
    """ListView for HistoryEntry with table of contents."""

    model = HistoryEntry
    template_name = "weblog/history_list.html"
    context_object_name = "history_entries"

    def get_queryset(self) -> QuerySet[HistoryEntry]:
        """Return only visible history entries in reverse chronological order."""
        return HistoryEntry.objects.filter(visible=True)


class BlogPostListView(ListView):
    """Public list of all published blog posts."""

    model = BlogPost
    template_name = "weblog/blogpost_list.html"
    context_object_name = "posts"
    paginate_by = 20

    def get_queryset(self) -> QuerySet[BlogPost]:
        """Return only published posts in reverse chronological order."""
        return BlogPost.objects.filter(published=True)


class BlogPostDetailView(DetailView):
    """Detail view for a single blog post."""

    model = BlogPost
    template_name = "weblog/blogpost_detail.html"
    context_object_name = "post"

    def get_queryset(self) -> QuerySet[BlogPost]:
        """Allow viewing published posts by all, unpublished by creator/staff only."""
        user = self.request.user
        base_qs = BlogPost.objects.all()

        # Staff can see everything
        if user.is_authenticated and getattr(user, "is_staff", False):
            return base_qs

        # Authenticated users can see published + their own unpublished
        if user.is_authenticated:
            return base_qs.filter(published=True) | base_qs.filter(creator=user)

        # Anonymous users see only published
        return base_qs.filter(published=True)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        post = self.object

        # Check if creator has a StaffPhotoListing for linking
        try:
            staff_listing = StaffPhotoListing.objects.get(user=post.creator)
            context["staff_listing"] = staff_listing
        except StaffPhotoListing.DoesNotExist:
            context["staff_listing"] = None

        return context


class BlogPostLandingView(LoginRequiredMixin, TemplateView):
    """Landing page for users to manage their blog posts."""

    template_name = "weblog/blogpost_landing.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # User's pending (unpublished) posts
        context["pending_posts"] = BlogPost.objects.filter(
            creator=user, published=False
        )

        # User's published posts
        context["published_posts"] = BlogPost.objects.filter(
            creator=user, published=True
        )

        # Check if user can create more posts (max 3 unpublished)
        context["can_create"] = context["pending_posts"].count() < 3

        return context


class BlogPostCreateView(LoginRequiredMixin, CreateView):
    """View for creating a new blog post draft."""

    model = BlogPost
    template_name = "weblog/blogpost_form.html"
    fields = ["title", "subtitle", "slug", "display_author", "content"]
    success_url = reverse_lazy("weblog:blog_landing")

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Check that user can create a new post before showing form."""
        if request.user.is_authenticated:
            unpublished_count = BlogPost.objects.filter(
                creator=request.user, published=False
            ).count()
            if unpublished_count >= 3:
                messages.error(
                    request,
                    "You already have 3 pending posts. Please wait for them to be "
                    "reviewed before creating more.",
                )
                return HttpResponseRedirect(str(self.success_url))
        response = super().dispatch(request, *args, **kwargs)
        assert isinstance(response, HttpResponse)
        return response

    def form_valid(self, form: Any) -> HttpResponse:
        """Set creator and published=False on save."""
        form.instance.creator = self.request.user
        form.instance.published = False
        messages.success(
            self.request,
            "Your blog post draft has been created and is pending review.",
        )
        return super().form_valid(form)


class BlogPostUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """View for editing an unpublished blog post."""

    model = BlogPost
    template_name = "weblog/blogpost_form.html"
    fields = ["title", "slug", "display_author", "content"]
    context_object_name = "post"

    def test_func(self) -> bool:
        """Only the creator can edit, and only while unpublished."""
        post = self.get_object()
        user = self.request.user
        return post.creator == user and not post.published

    def handle_no_permission(self) -> HttpResponse:
        """Show appropriate message when access is denied."""
        # Unauthenticated users should redirect to login
        if not self.request.user.is_authenticated:
            return super().handle_no_permission()

        # Authenticated users who fail test get 404
        post = self.get_object()
        if post.published:
            messages.error(
                self.request,
                "This post has been published and can no longer be edited. "
                "Contact an administrator for changes.",
            )
        else:
            messages.error(
                self.request, "You do not have permission to edit this post."
            )
        raise Http404("Post not found or not editable")

    def form_valid(self, form: Any) -> HttpResponse:
        messages.success(self.request, "Your blog post draft has been updated.")
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse("weblog:blog_landing")
