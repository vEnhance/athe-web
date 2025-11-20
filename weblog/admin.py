from django.contrib import admin

from .models import HistoryEntry


@admin.register(HistoryEntry)
class HistoryEntryAdmin(admin.ModelAdmin):
    """Admin interface for HistoryEntry."""

    list_display = ["title", "slug", "created_at", "visible"]
    list_filter = ["visible", "created_at"]
    search_fields = ["title", "content"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "created_at"
