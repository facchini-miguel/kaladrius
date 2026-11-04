from django.contrib import admin

from .models import TwoFactor


@admin.register(TwoFactor)
class DuasEtapasAdmin(admin.ModelAdmin):
    """Superusers can remove someone's two-step verification (lost phone); the secret is
    never shown here."""

    list_display = ["user", "ativa", "ativada_em"]
    list_filter = ["ativa"]
    search_fields = ["user__username"]
    fields = ["user", "ativa", "ativada_em"]
    readonly_fields = ["user", "ativa", "ativada_em"]

    def has_add_permission(self, request):
        return False
