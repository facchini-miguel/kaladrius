from django.contrib import admin

from .models import HealthPlan, MemberCard


@admin.register(HealthPlan)
class ConvenioAdmin(admin.ModelAdmin):
    list_display = ["name", "registration", "active", "clinic"]
    list_filter = ["clinic", "active"]
    search_fields = ["name", "registration"]


@admin.register(MemberCard)
class CarteirinhaAdmin(admin.ModelAdmin):
    list_display = ["patient", "convenio", "plano", "number", "valid_until", "active"]
    list_filter = ["clinic", "convenio", "active"]
    search_fields = ["number", "patient__name"]
    raw_id_fields = ["patient"]
