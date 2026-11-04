from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pacientes", "0002_paciente_arquivado")]

    operations = [
        migrations.AddField(
            model_name="paciente",
            name="whatsapp",
            field=models.CharField(
                blank=True,
                help_text="Com DDD. A ficha abre a conversa direto no WhatsApp.",
                max_length=11,
                verbose_name="WhatsApp",
            ),
        ),
    ]
