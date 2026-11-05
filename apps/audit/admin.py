from django.contrib import admin

from .models import AuditEntry


@admin.register(AuditEntry)
class AuditEntryAdmin(admin.ModelAdmin):
    """Read-only: audit entries are never created, changed or deleted by hand."""

    list_display = [
        "timestamp",
        "user_name",
        "action",
        "model_name",
        "object_repr",
        "clinic_id",
        "ip",
    ]
    list_filter = ["action", "model_name"]
    search_fields = ["user_name", "object_repr", "object_id"]
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
