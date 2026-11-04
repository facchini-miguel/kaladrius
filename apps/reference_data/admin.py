from django.contrib import admin

from .models import Bank, City, MaritalStatus, State


@admin.register(State)
class UFAdmin(admin.ModelAdmin):
    list_display = ["sigla", "name", "regiao", "code"]
    list_filter = ["regiao"]


@admin.register(City)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ["name", "uf", "code"]
    list_filter = ["uf"]
    search_fields = ["name"]
    list_select_related = ["uf"]


@admin.register(Bank)
class BancoAdmin(admin.ModelAdmin):
    list_display = ["code", "nome_curto", "name", "ispb"]
    search_fields = ["name", "nome_curto", "ispb"]


@admin.register(MaritalStatus)
class EstadoCivilAdmin(admin.ModelAdmin):
    list_display = ["name", "ordem"]
    list_editable = ["ordem"]
