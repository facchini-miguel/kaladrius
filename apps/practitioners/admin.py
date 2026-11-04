from django.contrib import admin

from .models import Practitioner


@admin.register(Practitioner)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ["nome", "clinica", "registro", "ativo"]
    list_filter = ["clinica", "ativo"]
    search_fields = ["nome", "registro"]
