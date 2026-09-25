from datetime import timedelta

from django.db import migrations, models
from django.db.models import F


def forwards(apps, schema_editor):
    CourseMeeting = apps.get_model("courses", "CourseMeeting")
    CourseMeeting.objects.filter(reminder_sent=True).update(
        reminder_sent_at=F("start_time") - timedelta(hours=24)
    )


def backwards(apps, schema_editor):
    CourseMeeting = apps.get_model("courses", "CourseMeeting")
    CourseMeeting.objects.filter(reminder_sent_at__isnull=False).update(
        reminder_sent=True
    )


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0027_course_is_office_hours_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursemeeting",
            name="reminder_sent_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the Discord reminder for this meeting was sent, if ever.",
                null=True,
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveField(
            model_name="coursemeeting",
            name="reminder_sent",
        ),
    ]
