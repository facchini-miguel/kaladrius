from django.contrib import admin

from .models import Agendamento, TipoAtendimento


@admin.register(TipoAtendimento)
class TipoAtendimentoAdmin(admin.ModelAdmin):
    list_display = ["nome", "clinica", "cor", "ativo"]
    list_filter = ["clinica", "ativo"]
    search_fields = ["nome"]


@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ["inicio", "fim", "profissional", "paciente", "tipo", "clinica"]
    list_filter = ["clinica", "profissional", "tipo"]
    search_fields = ["descricao", "paciente__nome"]
    date_hierarchy = "inicio"
    raw_id_fields = ["paciente"]
