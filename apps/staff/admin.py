from django.contrib import admin

from .models import Employee, Payroll


@admin.register(Employee)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ["name", "job_title", "hired_on", "active", "clinic"]
    list_filter = ["clinic", "active"]
    search_fields = ["name", "job_title"]


@admin.register(Payroll)
class FolhaAdmin(admin.ModelAdmin):
    list_display = ["employee", "period", "salary", "overtime_hours", "absences"]
    list_filter = ["clinic", "period"]
    raw_id_fields = ["employee", "entry"]
