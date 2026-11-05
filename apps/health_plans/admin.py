from django.contrib import admin

from .models import HealthPlan, MemberCard


@admin.register(HealthPlan)
class HealthPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "registration", "active", "clinic"]
    list_filter = ["clinic", "active"]
    search_fields = ["name", "registration"]


@admin.register(MemberCard)
class MemberCardAdmin(admin.ModelAdmin):
    list_display = ["patient", "health_plan", "plan", "number", "valid_until", "active"]
    list_filter = ["clinic", "health_plan", "active"]
    search_fields = ["number", "patient__name"]
    raw_id_fields = ["patient"]
