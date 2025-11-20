from django.contrib import admin

from .models import ApplyPSet, StaffPhotoListing


@admin.register(ApplyPSet)
class ApplyPSetAdmin(admin.ModelAdmin):
    """Admin interface for ApplyPSet."""

    list_display = ["name", "deadline", "status"]
    list_filter = ["status"]
    search_fields = ["name"]
    date_hierarchy = "deadline"


@admin.action(description="Mark selected staff as Past Staff (xstaff)")
def mark_as_past_staff(modeladmin, request, queryset):  # type: ignore
    """Change the category of selected staff members to xstaff (Past Staff)."""
    updated = queryset.update(category="xstaff")
    modeladmin.message_user(request, f"{updated} staff member(s) marked as Past Staff.")


@admin.register(StaffPhotoListing)
class StaffPhotoListingAdmin(admin.ModelAdmin):
    """Admin interface for StaffPhotoListing."""

    list_display = ["display_name", "role", "category", "ordering", "user"]
    list_filter = ["category"]
    search_fields = ["display_name", "role", "user__username"]
    autocomplete_fields = ("user",)
    actions = [mark_as_past_staff]
