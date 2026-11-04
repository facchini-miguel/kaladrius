from django.contrib import admin

from .models import Appointment, AppointmentType


@admin.register(AppointmentType)
class TipoAtendimentoAdmin(admin.ModelAdmin):
    list_display = ["nome", "clinic", "cor", "ativo"]
    list_filter = ["clinic", "ativo"]
    search_fields = ["nome"]


@admin.register(Appointment)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ["inicio", "fim", "profissional", "paciente", "tipo", "clinic"]
    list_filter = ["clinic", "profissional", "tipo"]
    search_fields = ["descricao", "paciente__nome"]
    date_hierarchy = "inicio"
    raw_id_fields = ["paciente"]
