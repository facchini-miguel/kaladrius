from django.contrib import admin

from .models import Carteirinha, Convenio


@admin.register(Convenio)
class ConvenioAdmin(admin.ModelAdmin):
    list_display = ["nome", "registro_ans", "ativo", "clinica"]
    list_filter = ["clinica", "ativo"]
    search_fields = ["nome", "registro_ans"]


@admin.register(Carteirinha)
class CarteirinhaAdmin(admin.ModelAdmin):
    list_display = ["paciente", "convenio", "plano", "numero", "validade", "ativa"]
    list_filter = ["clinica", "convenio", "ativa"]
    search_fields = ["numero", "paciente__nome"]
    raw_id_fields = ["paciente"]
