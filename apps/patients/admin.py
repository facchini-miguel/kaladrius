from django.contrib import admin

from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["name", "clinic", "kind", "tax_id", "mobile_phone", "active"]
    list_filter = ["clinic", "kind", "active"]
    search_fields = ["name", "legal_name", "tax_id"]
    autocomplete_fields = ["city"]
