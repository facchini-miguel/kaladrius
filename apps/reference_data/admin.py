from django.contrib import admin

from .models import Bank, City, MaritalStatus, State


@admin.register(State)
class UFAdmin(admin.ModelAdmin):
    list_display = ["sigla", "nome", "regiao", "codigo"]
    list_filter = ["regiao"]


@admin.register(City)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ["nome", "uf", "codigo"]
    list_filter = ["uf"]
    search_fields = ["nome"]
    list_select_related = ["uf"]


@admin.register(Bank)
class BancoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nome_curto", "nome", "ispb"]
    search_fields = ["nome", "nome_curto", "ispb"]


@admin.register(MaritalStatus)
class EstadoCivilAdmin(admin.ModelAdmin):
    list_display = ["nome", "ordem"]
    list_editable = ["ordem"]
