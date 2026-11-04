"""The models' names in English (decision 156). The tables keep their names (db_table), so
no SQL runs: an app rolled back to an older version still finds them."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("rechamadas", "0001_initial")]

    operations = [
        migrations.AlterModelTable(name="Rechamada", table="rechamadas_rechamada"),
        migrations.RenameModel(old_name="Rechamada", new_name="Recall"),
    ]
