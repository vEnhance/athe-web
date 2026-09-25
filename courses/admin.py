from django.contrib import admin

from courses.models import Course, CourseMeeting, GlobalEvent, Semester, Student


@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "start_date",
        "end_date",
        "house_points_freeze_date",
    )
    prepopulated_fields = {"slug": ("name",)}


class CourseMeetingInline(admin.TabularInline):
    model = CourseMeeting
    extra = 3
    fields = ("start_time", "title", "reminder_sent_at")


@admin.action(description="Activate Discord reminders for these Course objects")
def enable_discord_reminders(modeladmin, request, queryset):  # type: ignore
    updated = queryset.update(discord_reminders_enabled=True)
    modeladmin.message_user(request, f"{updated} courses updated.")


@admin.action(description="Deactivate Discord reminders for these Course objects")
def disable_discord_reminders(modeladmin, request, queryset):  # type: ignore
    updated = queryset.update(discord_reminders_enabled=False)
    modeladmin.message_user(request, f"{updated} courses updated.")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "kind",
        "semester",
        "instructor",
        "discord_reminders_enabled",
    )
    list_filter = ("kind", "semester")
    search_fields = ("name", "description")
    autocomplete_fields = ("instructor", "subscribed_staff")
    filter_horizontal = ("students", "student_organizers")
    inlines = [CourseMeetingInline]
    actions = [enable_discord_reminders, disable_discord_reminders]

    def formfield_for_manytomany(self, db_field, request, **kwargs):  # type: ignore
        """Filter students to only show students from the course's semester."""
        if db_field.name in ("students", "student_organizers"):
            # Get the course instance being edited
            course_id = request.resolver_match.kwargs.get("object_id")  # type: ignore[attr-defined]
            if course_id:
                try:
                    course = Course.objects.get(pk=course_id)
                    # Filter students to only those in the course's semester
                    kwargs["queryset"] = Student.objects.filter(
                        semester=course.semester
                    )
                except Course.DoesNotExist:
                    pass
        return super().formfield_for_manytomany(db_field, request, **kwargs)


# Admin actions for changing student houses
@admin.action(description="Assign selected students to Blob house")
def assign_to_blob(modeladmin, request, queryset):  # type: ignore
    updated = queryset.update(house=Student.House.BLOB)
    modeladmin.message_user(request, f"{updated} student(s) assigned to Blob house.")


@admin.action(description="Assign selected students to Cat house")
def assign_to_cat(modeladmin, request, queryset):  # type: ignore
    updated = queryset.update(house=Student.House.CAT)
    modeladmin.message_user(request, f"{updated} student(s) assigned to Cat house.")


@admin.action(description="Assign selected students to Owl house")
def assign_to_owl(modeladmin, request, queryset):  # type: ignore
    updated = queryset.update(house=Student.House.OWL)
    modeladmin.message_user(request, f"{updated} student(s) assigned to Owl house.")


@admin.action(description="Assign selected students to Red Panda house")
def assign_to_red_panda(modeladmin, request, queryset):  # type: ignore
    updated = queryset.update(house=Student.House.RED_PANDA)
    modeladmin.message_user(
        request, f"{updated} student(s) assigned to Red Panda house."
    )


@admin.action(description="Assign selected students to Bunny house")
def assign_to_bunny(modeladmin, request, queryset):  # type: ignore
    updated = queryset.update(house=Student.House.BUNNY)
    modeladmin.message_user(request, f"{updated} student(s) assigned to Bunny house.")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("user", "airtable_name", "semester", "house")
    list_display_links = ("user", "airtable_name")
    list_filter = ("semester", "house", ("user", admin.EmptyFieldListFilter))
    search_fields = (
        "user__username",
        "user__email",
        "airtable_name",
        "user__first_name",
        "user__last_name",
    )
    actions = [
        assign_to_blob,
        assign_to_cat,
        assign_to_owl,
        assign_to_red_panda,
        assign_to_bunny,
    ]


@admin.register(CourseMeeting)
class CourseMeetingAdmin(admin.ModelAdmin):
    list_display = ("course", "title", "start_time", "reminder_sent_at")
    list_filter = (
        ("reminder_sent_at", admin.EmptyFieldListFilter),
        "course__kind",
        "course__semester",
        "course",
    )
    search_fields = ("title", "course__name")
    date_hierarchy = "start_time"


@admin.register(GlobalEvent)
class GlobalEventAdmin(admin.ModelAdmin):
    list_display = ("title", "semester", "start_time")
    list_filter = ("semester", "start_time")
    search_fields = ("title", "description")
    date_hierarchy = "start_time"
