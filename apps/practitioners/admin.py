from django.contrib import admin

from .models import Practitioner


@admin.register(Practitioner)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ["name", "clinic", "registro", "active"]
    list_filter = ["clinic", "active"]
    search_fields = ["name", "registro"]
