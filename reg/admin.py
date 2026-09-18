from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html

from . import wizard
from .models import (
    CoursePreference,
    InviteLink,
    StaffInviteLink,
    StudentInviteLink,
    StudentRegistration,
)


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


class PagesDoneFilter(admin.SimpleListFilter):
    """How far through the questionnaire a student got, for chasing up the rest.

    The count lives inside a JSON list, which SQLite and MySQL disagree about
    how to measure, so the tallying happens in Python rather than in the query.
    """

    title = "pages done"
    parameter_name = "pages_done"

    def lookups(self, request: HttpRequest, model_admin: Any) -> list[tuple[str, str]]:
        total = len(wizard.STEPS)
        return [
            ("unfinished", "Unfinished (any)"),
            *((str(n), f"{n} of {total}") for n in range(total + 1)),
        ]

    def queryset(
        self, request: HttpRequest, queryset: QuerySet[StudentRegistration]
    ) -> QuerySet[StudentRegistration]:
        value = self.value()
        if value is None:
            return queryset
        if value == "unfinished":
            matches = (reg for reg in queryset if not wizard.is_complete(reg))
        else:
            matches = (reg for reg in queryset if wizard.done_count(reg) == int(value))
        return queryset.filter(pk__in=[reg.pk for reg in matches])


class CoursePreferenceInline(admin.TabularInline):  # type: ignore[type-arg]
    model = CoursePreference
    extra = 0
    fields = ["course", "rank", "already_taken"]
    ordering = ["already_taken", "rank"]


@admin.register(StudentRegistration)
class StudentRegistrationAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Read-only-ish view of what students told us; edits belong to the student."""

    list_display = [
        "student",
        "semester",
        "email",
        "discord_username",
        "pages_done",
        "updated_at",
    ]
    list_filter = ["student__semester", PagesDoneFilter]
    search_fields = [
        "student__airtable_name",
        "email",
        "parent_email",
        "discord_username",
    ]
    autocomplete_fields = ["student"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [CoursePreferenceInline]

    def get_queryset(self, request: HttpRequest) -> QuerySet[StudentRegistration]:
        return super().get_queryset(request).select_related("student__semester")

    @admin.display(description="Semester", ordering="student__semester")
    def semester(self, obj: StudentRegistration) -> str:
        return str(obj.student.semester)

    @admin.display(description="Pages done")
    def pages_done(self, obj: StudentRegistration) -> str:
        return f"{wizard.done_count(obj)}/{len(wizard.STEPS)}"
