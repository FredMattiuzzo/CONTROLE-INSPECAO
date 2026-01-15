from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("schedule", "0003_alter_scheduleentry_entry_type"),
    ]

    operations = [
        migrations.AddField(
            model_name="scheduleentry",
            name="client",
            field=models.CharField(max_length=255, null=True, blank=True),
        ),
    ]
