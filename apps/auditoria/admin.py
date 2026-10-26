from django.contrib import admin

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    """Read-only: audit entries are never created, changed or deleted by hand."""

    list_display = [
        "momento",
        "usuario_nome",
        "acao",
        "modelo",
        "objeto_descricao",
        "clinica_id",
        "ip",
    ]
    list_filter = ["acao", "modelo"]
    search_fields = ["usuario_nome", "objeto_descricao", "objeto_id"]
    date_hierarchy = "momento"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
