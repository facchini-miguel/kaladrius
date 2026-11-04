from django.contrib import admin

from .models import Appointment, AppointmentType


@admin.register(AppointmentType)
class TipoAtendimentoAdmin(admin.ModelAdmin):
    list_display = ["name", "clinic", "cor", "active"]
    list_filter = ["clinic", "active"]
    search_fields = ["name"]


@admin.register(Appointment)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ["inicio", "fim", "practitioner", "patient", "tipo", "clinic"]
    list_filter = ["clinic", "practitioner", "tipo"]
    search_fields = ["description", "patient__name"]
    date_hierarchy = "inicio"
    raw_id_fields = ["patient"]
