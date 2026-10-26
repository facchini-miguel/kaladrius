from django.contrib import admin

from .models import Rechamada


@admin.register(Rechamada)
class RechamadaAdmin(admin.ModelAdmin):
    list_display = ["data", "paciente", "descricao", "concluida", "clinica"]
    list_filter = ["clinica", "concluida"]
    search_fields = ["descricao", "paciente__nome"]
    date_hierarchy = "data"
    raw_id_fields = ["paciente"]
