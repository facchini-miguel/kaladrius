from django.contrib import admin

from .models import Practitioner


@admin.register(Practitioner)
class ProfissionalAdmin(admin.ModelAdmin):
    list_display = ["name", "clinic", "registration", "active"]
    list_filter = ["clinic", "active"]
    search_fields = ["name", "registration"]
