from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import BlogPost, HistoryEntry, Photo


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    """Admin interface for Photo."""

    list_display = ["name", "get_markdown_url", "uploaded_at"]
    search_fields = ["name"]
    date_hierarchy = "uploaded_at"
    readonly_fields = ["get_markdown_url", "uploaded_at"]

    def get_markdown_url(self, obj: Photo) -> str:
        """Display the markdown URL for copying."""
        return obj.markdown_url

    get_markdown_url.short_description = "Markdown URL"  # type: ignore


@admin.register(HistoryEntry)
class HistoryEntryAdmin(admin.ModelAdmin):
    """Admin interface for HistoryEntry."""

    list_display = ["title", "slug", "created_at", "visible"]
    list_filter = ["visible", "created_at"]
    search_fields = ["title", "content"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "created_at"


@admin.action(description="Publish selected blog posts")
def publish_posts(
    modeladmin: "BlogPostAdmin", request: HttpRequest, queryset: QuerySet[BlogPost]
) -> None:
    updated = queryset.update(published=True)
    modeladmin.message_user(request, f"{updated} blog post(s) published.")


@admin.action(description="Unpublish selected blog posts")
def unpublish_posts(
    modeladmin: "BlogPostAdmin", request: HttpRequest, queryset: QuerySet[BlogPost]
) -> None:
    updated = queryset.update(published=False)
    modeladmin.message_user(request, f"{updated} blog post(s) unpublished.")


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    """Admin interface for BlogPost."""

    list_display = ["title", "display_author", "display_date", "published", "creator"]
    list_filter = ["published", "display_date", "created_at"]
    search_fields = ["title", "subtitle", "content", "display_author"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "display_date"
    autocomplete_fields = ("creator",)
    readonly_fields = ["created_at", "updated_at"]
    actions = [publish_posts, unpublish_posts]
    fieldsets = (
        (None, {"fields": ("title", "subtitle", "slug", "display_author", "creator")}),
        ("Content", {"fields": ("content",)}),
        (
            "Publication",
            {"fields": ("published", "display_date", "created_at", "updated_at")},
        ),
    )
