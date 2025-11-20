from django.contrib import admin

from .models import HistoryEntry, Photo


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
