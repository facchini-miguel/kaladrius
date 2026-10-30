from django.contrib import admin

from .models import Folha, Funcionario


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ["nome", "cargo", "admissao", "ativo", "clinica"]
    list_filter = ["clinica", "ativo"]
    search_fields = ["nome", "cargo"]


@admin.register(Folha)
class FolhaAdmin(admin.ModelAdmin):
    list_display = ["funcionario", "competencia", "salario", "horas_extras", "faltas"]
    list_filter = ["clinica", "competencia"]
    raw_id_fields = ["funcionario", "lancamento"]
