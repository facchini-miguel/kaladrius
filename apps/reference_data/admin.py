from django.contrib import admin

from .models import Bank, City, MaritalStatus, State


@admin.register(State)
class UFAdmin(admin.ModelAdmin):
    list_display = ["abbreviation", "name", "region", "code"]
    list_filter = ["region"]


@admin.register(City)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ["name", "state", "code"]
    list_filter = ["state"]
    search_fields = ["name"]
    list_select_related = ["state"]


@admin.register(Bank)
class BancoAdmin(admin.ModelAdmin):
    list_display = ["code", "short_name", "name", "ispb"]
    search_fields = ["name", "short_name", "ispb"]


@admin.register(MaritalStatus)
class EstadoCivilAdmin(admin.ModelAdmin):
    list_display = ["name", "sort_order"]
    list_editable = ["sort_order"]
