from django.contrib import admin

from .models import DuasEtapas


@admin.register(DuasEtapas)
class DuasEtapasAdmin(admin.ModelAdmin):
    """Superusers can remove someone's two-step verification (lost phone); the secret is
    never shown here."""

    list_display = ["usuario", "ativa", "ativada_em"]
    list_filter = ["ativa"]
    search_fields = ["usuario__username"]
    fields = ["usuario", "ativa", "ativada_em"]
    readonly_fields = ["usuario", "ativa", "ativada_em"]

    def has_add_permission(self, request):
        return False
