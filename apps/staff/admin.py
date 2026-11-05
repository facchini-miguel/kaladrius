from django.contrib import admin

from .models import Employee, Payroll


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["name", "job_title", "hired_on", "active", "clinic"]
    list_filter = ["clinic", "active"]
    search_fields = ["name", "job_title"]


@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ["employee", "period", "salary", "overtime_hours", "absences"]
    list_filter = ["clinic", "period"]
    raw_id_fields = ["employee", "entry"]
