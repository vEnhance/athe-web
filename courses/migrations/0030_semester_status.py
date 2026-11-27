from django.db import migrations, models
from django.utils import timezone


def forwards(apps, schema_editor):
    Semester = apps.get_model("courses", "Semester")
    today = timezone.localdate()
    for semester in Semester.objects.all():
        if not semester.visible:
            semester.status = "internal_draft"
        elif semester.end_date < today:
            semester.status = "ended"
        elif semester.start_date <= today:
            semester.status = "started"
        else:
            semester.status = "public_draft"
        semester.save(update_fields=["status"])


def backwards(apps, schema_editor):
    Semester = apps.get_model("courses", "Semester")
    Semester.objects.filter(status="internal_draft").update(visible=False)


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0029_course_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="semester",
            name="status",
            field=models.CharField(
                choices=[
                    ("internal_draft", "Internal draft"),
                    ("public_draft", "Public draft"),
                    ("public_finalized", "Public finalized"),
                    ("started", "Started"),
                    ("ended", "Ended"),
                ],
                default="internal_draft",
                help_text="Internal draft: hidden from non-staff, still being put together. Public draft: shown to everyone, but the course list is marked as still being updated. Public finalized: shown with the course list complete. Started: underway; at most one semester can be started at a time. Ended: over. Nothing changes status on its own; flip it by hand.",
                max_length=20,
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="semester",
            name="visible",
        ),
        migrations.AlterField(
            model_name="semester",
            name="end_date",
            field=models.DateField(
                help_text="When this semester ends. Used for display and scheduling meetings; whether the semester has ended is the status."
            ),
        ),
        migrations.AlterField(
            model_name="semester",
            name="start_date",
            field=models.DateField(
                help_text="When this semester starts. Used for ordering, display, and scheduling meetings; whether the semester has started is the status."
            ),
        ),
        migrations.AddConstraint(
            model_name="semester",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "started")),
                fields=("status",),
                name="at_most_one_started_semester",
                violation_error_message="Another semester is already started; mark it ended first.",
            ),
        ),
    ]
