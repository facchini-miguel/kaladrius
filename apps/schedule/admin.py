from django.contrib import admin

from .models import Appointment, AppointmentType


@admin.register(AppointmentType)
class AppointmentTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "clinic", "color", "active"]
    list_filter = ["clinic", "active"]
    search_fields = ["name"]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ["start", "end", "practitioner", "patient", "kind", "clinic"]
    list_filter = ["clinic", "practitioner", "kind"]
    search_fields = ["description", "patient__name"]
    date_hierarchy = "start"
    raw_id_fields = ["patient"]
