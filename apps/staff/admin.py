from django.contrib import admin

from .models import Employee, Payroll


@admin.register(Employee)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ["nome", "cargo", "admissao", "ativo", "clinic"]
    list_filter = ["clinic", "ativo"]
    search_fields = ["nome", "cargo"]


@admin.register(Payroll)
class FolhaAdmin(admin.ModelAdmin):
    list_display = ["funcionario", "competencia", "salario", "horas_extras", "faltas"]
    list_filter = ["clinic", "competencia"]
    raw_id_fields = ["funcionario", "lancamento"]
