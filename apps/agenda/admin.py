from django.contrib import admin

from .models import TipoAtendimento


@admin.register(TipoAtendimento)
class TipoAtendimentoAdmin(admin.ModelAdmin):
    list_display = ["nome", "clinica", "cor", "ativo"]
    list_filter = ["clinica", "ativo"]
    search_fields = ["nome"]
