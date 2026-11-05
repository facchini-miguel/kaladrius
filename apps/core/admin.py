from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_noop

from .forms import ClinicAdminForm
from .models import Backup, Clinic, Membership, Usuario


def _superuser_only(request):
    # The admin works across every clinic, so only platform superusers may use it.
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = _superuser_only

# Django 6.1 has no Portuguese or Spanish text for the blank option of the admin's lists
# (actions, filters): marked here so the project's catalogs translate it (review, superuser).
gettext_noop("- Select an option -")


class ClinicMembershipInline(admin.TabularInline):
    model = Membership
    fk_name = "clinic"
    extra = 0
    autocomplete_fields = ["user"]


class UserMembershipInline(admin.TabularInline):
    model = Membership
    fk_name = "user"
    extra = 0


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    form = ClinicAdminForm
    list_display = [
        "name",
        "document",
        "active",
        "schedule_start",
        "schedule_end",
        "schedule_interval",
    ]
    list_filter = ["active"]
    search_fields = ["name", "document"]
    inlines = [ClinicMembershipInline]

    def has_add_permission(self, request):
        # One installation, one clinic (decision 069): the first one is registered on the
        # first access (core:cadastrar_clinica).
        return super().has_add_permission(request) and not Clinic.objects.exists()


@admin.register(Usuario)
class ClinicUserAdmin(UserAdmin):
    inlines = [UserMembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "clinic", "role", "active"]
    list_filter = ["role", "active", "clinic"]
    search_fields = ["user__username", "clinic__name"]


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    """Read-only list of the backups recorded by the server."""

    list_display = ["timestamp", "file", "size"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
