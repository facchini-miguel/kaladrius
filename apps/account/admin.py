from django.contrib import admin

from .models import TwoFactor


@admin.register(TwoFactor)
class DuasEtapasAdmin(admin.ModelAdmin):
    """Superusers can remove someone's two-step verification (lost phone); the secret is
    never shown here."""

    list_display = ["user", "active", "activated_at"]
    list_filter = ["active"]
    search_fields = ["user__username"]
    fields = ["user", "active", "activated_at"]
    readonly_fields = ["user", "active", "activated_at"]

    def has_add_permission(self, request):
        return False
