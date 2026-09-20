from django.contrib import admin

from .models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("title", "student", "destination", "created_at", "resolved_at")
    list_filter = ("meeting__course", "student__semester")
    search_fields = ("title", "question", "student__airtable_name")
    autocomplete_fields = ("student",)
    readonly_fields = ("created_at",)
