from django.contrib import admin

from .models import HealthPlan, MemberCard


@admin.register(HealthPlan)
class ConvenioAdmin(admin.ModelAdmin):
    list_display = ["nome", "registro", "ativo", "clinic"]
    list_filter = ["clinic", "ativo"]
    search_fields = ["nome", "registro"]


@admin.register(MemberCard)
class CarteirinhaAdmin(admin.ModelAdmin):
    list_display = ["patient", "convenio", "plano", "numero", "validade", "ativa"]
    list_filter = ["clinic", "convenio", "ativa"]
    search_fields = ["numero", "patient__nome"]
    raw_id_fields = ["patient"]
