from django.contrib import admin

from .models import YearbookEntry


@admin.register(YearbookEntry)
class YearbookEntryAdmin(admin.ModelAdmin):
    list_display = ("display_name", "student", "get_semester", "get_house")
    list_filter = ("student__semester", "student__house")
    search_fields = (
        "display_name",
        "student__airtable_name",
        "student__user__username",
    )
    autocomplete_fields = ("student",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Semester", ordering="student__semester")
    def get_semester(self, obj: YearbookEntry) -> str:
        return str(obj.student.semester)

    @admin.display(description="House", ordering="student__house")
    def get_house(self, obj: YearbookEntry) -> str:
        return obj.student.get_house_display()
