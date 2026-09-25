from django.db import migrations, models


def forwards(apps, schema_editor):
    Course = apps.get_model("courses", "Course")
    Course.objects.filter(is_club=True).update(kind="club")
    Course.objects.filter(is_office_hours=True).update(kind="office_hours")


def backwards(apps, schema_editor):
    Course = apps.get_model("courses", "Course")
    Course.objects.exclude(kind="class").update(is_club=True)
    Course.objects.filter(kind="office_hours").update(is_office_hours=True)


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0028_coursemeeting_reminder_sent_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="course",
            name="kind",
            field=models.CharField(
                choices=[
                    ("class", "Class"),
                    ("club", "Club/Event"),
                    ("office_hours", "Office hours"),
                ],
                default="class",
                help_text="Office hours are a club whose meetings students may "
                "send questions to.",
                max_length=20,
            ),
        ),
        migrations.RunPython(forwards, backwards),
        migrations.RemoveConstraint(
            model_name="course",
            name="office_hours_must_be_a_club",
        ),
        migrations.RemoveField(
            model_name="course",
            name="is_club",
        ),
        migrations.RemoveField(
            model_name="course",
            name="is_office_hours",
        ),
        migrations.AlterModelOptions(
            name="course",
            options={"ordering": ("-semester__start_date", "kind", "name")},
        ),
    ]
