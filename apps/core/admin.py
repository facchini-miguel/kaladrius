from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Backup, Clinica, Usuario, Vinculo


def _somente_superusuario(request):
    # The admin works across every clinic, so only platform superusers may use it.
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = _somente_superusuario


class VinculoNaClinicaInline(admin.TabularInline):
    model = Vinculo
    fk_name = "clinica"
    extra = 0
    autocomplete_fields = ["usuario"]


class VinculoDoUsuarioInline(admin.TabularInline):
    model = Vinculo
    fk_name = "usuario"
    extra = 0


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display = ["nome", "documento", "ativa", "agenda_inicio", "agenda_fim", "agenda_intervalo"]
    list_filter = ["ativa"]
    search_fields = ["nome", "documento"]
    inlines = [VinculoNaClinicaInline]

    def has_add_permission(self, request):
        # One installation, one clinic (decision 069): the first one is registered on the
        # first access (core:cadastrar_clinica).
        return super().has_add_permission(request) and not Clinica.objects.exists()


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    inlines = [VinculoDoUsuarioInline]


@admin.register(Vinculo)
class VinculoAdmin(admin.ModelAdmin):
    list_display = ["usuario", "clinica", "papel", "ativo"]
    list_filter = ["papel", "ativo", "clinica"]
    search_fields = ["usuario__username", "clinica__nome"]


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    """Read-only list of the backups recorded by the server."""

    list_display = ["momento", "arquivo", "tamanho"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
