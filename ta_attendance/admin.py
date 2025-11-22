from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ["user", "date", "club"]
    list_filter = ["date", "club", "club__semester"]
    search_fields = [
        "user__username",
        "user__first_name",
        "user__last_name",
        "club__name",
    ]
    autocomplete_fields = ["user", "club"]
    date_hierarchy = "date"
