# Throwaway migration of a test pull request (decision 139): never merged.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0018_numeracao_dentaria")]

    operations = [migrations.RunSQL("SELECT 1", reverse_sql="SELECT 1")]
