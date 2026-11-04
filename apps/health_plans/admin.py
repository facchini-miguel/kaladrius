from django.contrib import admin

from .models import HealthPlan, MemberCard


@admin.register(HealthPlan)
class ConvenioAdmin(admin.ModelAdmin):
    list_display = ["nome", "registro", "ativo", "clinica"]
    list_filter = ["clinica", "ativo"]
    search_fields = ["nome", "registro"]


@admin.register(MemberCard)
class CarteirinhaAdmin(admin.ModelAdmin):
    list_display = ["paciente", "convenio", "plano", "numero", "validade", "ativa"]
    list_filter = ["clinica", "convenio", "ativa"]
    search_fields = ["numero", "paciente__nome"]
    raw_id_fields = ["paciente"]
