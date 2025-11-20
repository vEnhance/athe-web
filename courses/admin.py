from django.contrib import admin

from courses.models import Course, CourseMeeting, Semester, Student


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


@admin.register(CourseMeeting)
class CourseMeetingAdmin(admin.ModelAdmin):
    list_display = ("course", "title", "start_time", "reminder_sent")
    list_filter = ("course", "reminder_sent", "start_time")
    search_fields = ("title", "course__name")
    date_hierarchy = "start_time"
