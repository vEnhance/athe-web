from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html

from .models import InviteLink, StaffInviteLink, StudentInviteLink


class InviteLinkAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Shared admin for invite links; subclasses supply their own editable fields."""

    #: Fields shown in the first fieldset, above the generated link.
    edit_fields: list[str] = ["name", "expiration_date"]

    list_filter = ["expiration_date", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["id", "created_at", "link"]

    def get_fieldsets(
        self, request: HttpRequest, obj: InviteLink | None = None
    ) -> list[tuple[str | None, dict[str, list[str]]]]:
        return [
            (None, {"fields": self.edit_fields}),
            ("Link Information", {"fields": ["id", "created_at", "link"]}),
        ]

    @admin.display(description="Invite Link")
    def link(self, obj: InviteLink) -> str:
        """Display the invite link URL path."""
        if not obj.pk:
            return "-"
        url = obj.get_absolute_url()
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)


@admin.register(StaffInviteLink)
class StaffInviteLinkAdmin(InviteLinkAdmin):
    list_display = ["name", "expiration_date", "created_at", "is_expired", "link"]


@admin.register(StudentInviteLink)
class StudentInviteLinkAdmin(InviteLinkAdmin):
    edit_fields = ["name", "semester", "expiration_date"]

    list_display = [
        "name",
        "semester",
        "expiration_date",
        "created_at",
        "is_expired",
        "is_semester_ended",
        "link",
    ]
    list_filter = ["semester", "expiration_date", "created_at"]
