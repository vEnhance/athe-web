from django.contrib import admin
from django.utils.html import format_html

from .models import StaffInviteLink


@admin.register(StaffInviteLink)
class StaffInviteLinkAdmin(admin.ModelAdmin):
    list_display = ["name", "expiration_date", "created_at", "is_expired", "link"]
    list_filter = ["expiration_date", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "link"]
    fieldsets = [
        (
            None,
            {
                "fields": ["name", "expiration_date"],
            },
        ),
        (
            "Link Information",
            {
                "fields": ["id", "created_at", "link"],
            },
        ),
    ]

    def link(self, obj: StaffInviteLink) -> str:
        """Display the full invite link as a clickable URL."""
        if obj.pk:
            url = obj.get_absolute_url()
            full_url = f"http://localhost:8000{url}"  # For development
            return format_html(
                '<a href="{}" target="_blank">{}</a>', full_url, full_url
            )
        return "-"

    link.short_description = "Invite Link"  # type: ignore
