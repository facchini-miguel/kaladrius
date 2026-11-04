from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_noop

from .forms import ClinicaAdminForm
from .models import Backup, Clinic, Membership, Usuario


def _somente_superusuario(request):
    # The admin works across every clinic, so only platform superusers may use it.
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = _somente_superusuario

# Django 6.1 has no Portuguese or Spanish text for the blank option of the admin's lists
# (actions, filters): marked here so the project's catalogs translate it (review, superuser).
gettext_noop("- Select an option -")


class VinculoNaClinicaInline(admin.TabularInline):
    model = Membership
    fk_name = "clinic"
    extra = 0
    autocomplete_fields = ["user"]


class VinculoDoUsuarioInline(admin.TabularInline):
    model = Membership
    fk_name = "user"
    extra = 0


@admin.register(Clinic)
class ClinicaAdmin(admin.ModelAdmin):
    form = ClinicaAdminForm
    list_display = [
        "name",
        "documento",
        "active",
        "agenda_inicio",
        "agenda_fim",
        "agenda_intervalo",
    ]
    list_filter = ["active"]
    search_fields = ["name", "documento"]
    inlines = [VinculoNaClinicaInline]

    def has_add_permission(self, request):
        # One installation, one clinic (decision 069): the first one is registered on the
        # first access (core:cadastrar_clinica).
        return super().has_add_permission(request) and not Clinic.objects.exists()


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    inlines = [VinculoDoUsuarioInline]


@admin.register(Membership)
class VinculoAdmin(admin.ModelAdmin):
    list_display = ["user", "clinic", "papel", "active"]
    list_filter = ["papel", "active", "clinic"]
    search_fields = ["user__username", "clinic__name"]


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    """Read-only list of the backups recorded by the server."""

    list_display = ["momento", "arquivo", "tamanho"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
