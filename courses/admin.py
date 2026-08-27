from django.contrib import admin, messages

from courses.models import Course, CourseMeeting, GlobalEvent, Semester, Student


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


@admin.action(description="Add instructor to leaders for selected courses")
def add_instructor_to_leaders(modeladmin, request, queryset):  # type: ignore
    """Repair courses whose leaders are missing their instructor."""
    repaired = 0
    unlinked = []
    for course in queryset.select_related("instructor__user"):
        if course.ensure_instructor_is_leader():
            repaired += 1
        elif course.instructor is None or course.instructor.user is None:
            unlinked.append(course)
    modeladmin.message_user(
        request,
        f"Added the instructor as a leader on {repaired} course(s); "
        "the rest already had theirs.",
    )
    if unlinked:
        names = ", ".join(str(course) for course in unlinked)
        modeladmin.message_user(
            request,
            f"No instructor account to add for: {names}. Set an instructor on the "
            "course, and a user on that staff photo listing, then run this again.",
            level=messages.WARNING,
        )


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
    list_display = (
        "name",
        "is_club",
        "semester",
        "instructor",
        "discord_reminders_enabled",
    )
    list_filter = ("is_club", "semester", "difficulty")
    search_fields = ("name", "description")
    autocomplete_fields = ("instructor",)
    filter_horizontal = ("leaders", "students")
    inlines = [CourseMeetingInline]
    actions = [add_instructor_to_leaders]

    def save_related(self, request, form, formsets, change) -> None:  # type: ignore
        """Re-add the instructor as a leader once the form's own m2m data lands.

        ``Course.save`` adds the instructor, but the admin writes the leaders
        widget afterwards and that write replaces the whole set. Saving a course
        without picking the instructor in the leaders box therefore dropped them
        straight back out again, which is how courses ended up needing the
        ``add_instructor_to_leaders`` action above.
        """
        super().save_related(request, form, formsets, change)
        form.instance.ensure_instructor_is_leader()

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
    list_display = ("course", "title", "start_time", "reminder_sent")
    list_filter = (
        "reminder_sent",
        "course__is_club",
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
