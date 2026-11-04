from django.contrib import admin

from .models import Employee, Payroll


@admin.register(Employee)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ["name", "cargo", "admissao", "active", "clinic"]
    list_filter = ["clinic", "active"]
    search_fields = ["name", "cargo"]


@admin.register(Payroll)
class FolhaAdmin(admin.ModelAdmin):
    list_display = ["employee", "competencia", "salario", "horas_extras", "faltas"]
    list_filter = ["clinic", "competencia"]
    raw_id_fields = ["employee", "entry"]
