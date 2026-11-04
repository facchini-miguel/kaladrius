from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ["nome", "clinic", "tipo", "cpf_cnpj", "telefone_celular", "ativo"]
    list_filter = ["clinic", "tipo", "ativo"]
    search_fields = ["nome", "razao_social", "cpf_cnpj"]
    autocomplete_fields = ["cidade"]
