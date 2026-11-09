"""AuditEntry.event and event_values (decision 206): what the system describes itself, as a
code and its values, shown in the reader's language. Entries written before keep only
their Portuguese text (apps/audit/events.py reads it)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("audit", "0009_english_texts")]

    operations = [
        migrations.AddField(
            model_name="auditentry",
            name="event",
            field=models.CharField(blank=True, max_length=30, verbose_name="event"),
        ),
        migrations.AddField(
            model_name="auditentry",
            name="event_values",
            field=models.JSONField(blank=True, default=dict, verbose_name="event values"),
        ),
    ]
