from django.contrib import admin

from .models import StaffPhotoListing


@admin.register(StaffPhotoListing)
class StaffPhotoListingAdmin(admin.ModelAdmin):
    """Admin interface for StaffPhotoListing."""

    list_display = ["display_name", "role", "category", "ordering", "user"]
    list_filter = ["category"]
    search_fields = ["display_name", "role", "user__username"]
    autocomplete_fields = ("user",)
