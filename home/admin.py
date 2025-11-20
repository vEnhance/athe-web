from django.contrib import admin

from .models import ApplyPSet, StaffPhotoListing


@admin.register(ApplyPSet)
class ApplyPSetAdmin(admin.ModelAdmin):
    """Admin interface for ApplyPSet."""

    list_display = ["name", "deadline", "status"]
    list_filter = ["status"]
    search_fields = ["name"]
    date_hierarchy = "deadline"


@admin.register(StaffPhotoListing)
class StaffPhotoListingAdmin(admin.ModelAdmin):
    """Admin interface for StaffPhotoListing."""

    list_display = ["display_name", "role", "category", "ordering", "user"]
    list_filter = ["category"]
    search_fields = ["display_name", "role", "user__username"]
    autocomplete_fields = ("user",)
