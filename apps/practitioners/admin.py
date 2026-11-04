from django.contrib import admin

from .models import Practitioner


@admin.register(Practitioner)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ["nome", "clinic", "registro", "ativo"]
    list_filter = ["clinic", "ativo"]
    search_fields = ["nome", "registro"]
