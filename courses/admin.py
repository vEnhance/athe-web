from django.contrib import admin

from courses.models import Course, CourseMeeting, Semester, Student


# Admin actions for changing student houses
@admin.action(description="Assign selected students to Blob house")
def assign_to_blob(modeladmin, request, queryset):  # type: ignore
    """Change the house of selected students to Blob."""
    updated = queryset.update(house=Student.House.BLOB)
    modeladmin.message_user(request, f"{updated} student(s) assigned to Blob house.")


@admin.action(description="Assign selected students to Cat house")
def assign_to_cat(modeladmin, request, queryset):  # type: ignore
    """Change the house of selected students to Cat."""
    updated = queryset.update(house=Student.House.CAT)
    modeladmin.message_user(request, f"{updated} student(s) assigned to Cat house.")


@admin.action(description="Assign selected students to Owl house")
def assign_to_owl(modeladmin, request, queryset):  # type: ignore
    """Change the house of selected students to Owl."""
    updated = queryset.update(house=Student.House.OWL)
    modeladmin.message_user(request, f"{updated} student(s) assigned to Owl house.")


@admin.action(description="Assign selected students to Red Panda house")
def assign_to_red_panda(modeladmin, request, queryset):  # type: ignore
    """Change the house of selected students to Red Panda."""
    updated = queryset.update(house=Student.House.RED_PANDA)
    modeladmin.message_user(
        request, f"{updated} student(s) assigned to Red Panda house."
    )


@admin.action(description="Assign selected students to Bunny house")
def assign_to_bunny(modeladmin, request, queryset):  # type: ignore
    """Change the house of selected students to Bunny."""
    updated = queryset.update(house=Student.House.BUNNY)
    modeladmin.message_user(request, f"{updated} student(s) assigned to Bunny house.")


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
    fields = ("start_time", "title", "reminder_sent")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "is_club", "semester", "instructor")
    list_filter = ("is_club", "semester", "difficulty")
    search_fields = ("name", "description")
    autocomplete_fields = ("instructor",)
    filter_horizontal = ("leaders", "students")
    inlines = [CourseMeetingInline]

    def formfield_for_manytomany(self, db_field, request, **kwargs):  # type: ignore
        """Filter students to only show students from the course's semester."""
        if db_field.name == "students":
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


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("user", "semester", "house")
    list_filter = ("semester", "house")
    search_fields = ("user__username", "user__email")
    actions = [
        assign_to_blob,
        assign_to_cat,
        assign_to_owl,
        assign_to_red_panda,
        assign_to_bunny,
    ]


@admin.register(CourseMeeting)
class CourseMeetingAdmin(admin.ModelAdmin):
    list_display = ("course", "title", "start_time", "reminder_sent")
    list_filter = ("course", "reminder_sent", "start_time")
    search_fields = ("title", "course__name")
    date_hierarchy = "start_time"
