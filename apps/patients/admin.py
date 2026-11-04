from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ["name", "clinic", "tipo", "cpf_cnpj", "telefone_celular", "active"]
    list_filter = ["clinic", "tipo", "active"]
    search_fields = ["name", "razao_social", "cpf_cnpj"]
    autocomplete_fields = ["cidade"]
