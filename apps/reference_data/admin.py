from django.contrib import admin

from .models import UF, Banco, Cidade, EstadoCivil


@admin.register(UF)
class UFAdmin(admin.ModelAdmin):
    list_display = ["sigla", "nome", "regiao", "codigo"]
    list_filter = ["regiao"]


@admin.register(Cidade)
class CidadeAdmin(admin.ModelAdmin):
    list_display = ["nome", "uf", "codigo"]
    list_filter = ["uf"]
    search_fields = ["nome"]
    list_select_related = ["uf"]


@admin.register(Banco)
class BancoAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nome_curto", "nome", "ispb"]
    search_fields = ["nome", "nome_curto", "ispb"]


@admin.register(EstadoCivil)
class EstadoCivilAdmin(admin.ModelAdmin):
    list_display = ["nome", "ordem"]
    list_editable = ["ordem"]
