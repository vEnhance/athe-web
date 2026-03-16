from django.contrib import admin
from django.http import HttpRequest

from housepoints.models import Award


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = (
        "get_recipient",
        "award_type",
        "points",
        "house",
        "semester",
        "awarded_at",
        "awarded_by",
    )
    list_filter = ("semester", "house", "award_type", "awarded_at")
    search_fields = (
        "student__user__username",
        "student__user__email",
        "description",
    )
    date_hierarchy = "awarded_at"
    autocomplete_fields = ("student", "awarded_by")
    readonly_fields = ("created_at",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "semester",
                    "student",
                    "house",
                    "award_type",
                    "points",
                    "description",
                )
            },
        ),
        (
            "Metadata",
            {
                "fields": ("awarded_at", "awarded_by", "created_at"),
            },
        ),
    )

    def get_recipient(self, obj: Award) -> str:
        """Display recipient as either student username or house name."""
        if obj.student:
            return str(obj.student)
        return f"{obj.get_house_display()} (House)"  # type: ignore[attr-defined]

    get_recipient.short_description = "Recipient"  # type: ignore[attr-defined]

    def save_model(
        self,
        request: HttpRequest,
        obj: Award,
        form,
        change: bool,  # type: ignore[no-untyped-def]
    ) -> None:
        """Auto-set awarded_by to current user if not set."""
        if not obj.awarded_by:
            obj.awarded_by = request.user
        super().save_model(request, obj, form, change)
