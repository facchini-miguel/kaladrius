"""Role-based permissions per clinic.

Each role (Papel) gets a set of actions (Acao) per module (Modulo). The same check
guards the views (server side) and decides which menus and buttons the templates show.
Platform superusers can do everything in any clinic, turned-off modules included
(decision 115: marked as off; the team does not see them).
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _

from . import modules
from .models import ModuleCode, Role


class Module(models.TextChoices):
    PATIENTS = "pacientes", _("Pacientes")
    SCHEDULE = "agenda", _("Agenda")
    RECALLS = "rechamadas", _("Rechamadas")
    BIRTHDAYS = "aniversariantes", _("Aniversariantes")
    PRACTITIONERS = "profissionais", _("Profissionais")
    CATALOGS = "cadastros", _("Tabelas base")
    USERS = "usuarios", _("Usuários da clínica")
    CLINIC = "clinic", _("Configurações da clínica")
    AUDIT = "auditoria", _("Auditoria")
    # Receivables, receiving payments, receipts and debtors (front desk included).
    RECEIVING = "recebimentos", _("Recebimentos")
    # Accounts, categories and (0.16) payables and cash flow: administrators only.
    FINANCE = "financeiro", _("Financeiro")
    # Treatment estimates (0.18.0): written by practitioners and the front desk.
    ESTIMATES = "orcamentos", _("Orçamentos")
    # Health plans and the patients' cards (decision 094).
    HEALTH_PLANS = "convenios", _("Convênios")
    # Staff, salaries and the month's pay (decision 099): administrators and Finance only.
    STAFF = "pessoal", _("Pessoal")


class Action(models.TextChoices):
    VIEW = "ver", _("Ver")
    CREATE = "criar", _("Criar")
    CHANGE = "alterar", _("Alterar")
    DELETE = "excluir", _("Excluir")


_ALL = frozenset(Action)
_VIEW = frozenset({Action.VIEW})
_NO_DELETE = frozenset({Action.VIEW, Action.CREATE, Action.CHANGE})

# Default permission matrix. To be reviewed with the owner after phase 1.
MATRIX = {
    Role.ADMIN: {modulo: _ALL for modulo in Module},
    Role.FRONT_DESK: {
        Module.PATIENTS: _NO_DELETE,
        Module.SCHEDULE: _ALL,
        Module.RECALLS: _ALL,
        Module.BIRTHDAYS: _VIEW,
        Module.PRACTITIONERS: _VIEW,
        Module.CATALOGS: _VIEW,
        # Cancelling entries, reversing payments and discounts stay with administrators.
        Module.RECEIVING: _NO_DELETE,
        Module.ESTIMATES: _NO_DELETE,
        Module.HEALTH_PLANS: _NO_DELETE,
    },
    # All of finance, and only a look at who the money is about (decision 088).
    Role.FINANCE: {
        Module.RECEIVING: _ALL,
        Module.FINANCE: _ALL,
        Module.STAFF: _ALL,
        Module.PATIENTS: _VIEW,
        Module.ESTIMATES: _VIEW,
        Module.PRACTITIONERS: _VIEW,
        Module.CATALOGS: _VIEW,
        Module.HEALTH_PLANS: _VIEW,
    },
    Role.PRACTITIONER: {
        Module.PATIENTS: _NO_DELETE,
        Module.SCHEDULE: _NO_DELETE,
        Module.RECALLS: _NO_DELETE,
        Module.BIRTHDAYS: _VIEW,
        Module.PRACTITIONERS: _VIEW,
        Module.CATALOGS: _VIEW,
        Module.ESTIMATES: _NO_DELETE,
        Module.HEALTH_PLANS: _VIEW,
    },
}


# The public demo logins (decision 089) only look at the team and the clinic settings: a
# published password must never create users, reset others' passwords or rename the clinic.
READ_ONLY_IN_DEMO = frozenset({Module.USERS, Module.CLINIC})

# The clinic module (decision 092) each permission module belongs to; the rest is the core.
CLINIC_MODULE = {
    Module.SCHEDULE: ModuleCode.SCHEDULE,
    Module.RECALLS: ModuleCode.RECALLS,
    Module.BIRTHDAYS: ModuleCode.BIRTHDAYS,
    Module.RECEIVING: ModuleCode.FINANCE,
    Module.FINANCE: ModuleCode.FINANCE,
    Module.ESTIMATES: ModuleCode.ESTIMATES,
    Module.HEALTH_PLANS: ModuleCode.HEALTH_PLANS,
    Module.STAFF: ModuleCode.STAFF,
}


def can(request, modulo, acao):
    """Whether the current user may perform `acao` on `modulo` in the current clinic."""
    user = request.user
    if not user.is_authenticated or getattr(request, "clinic", None) is None:
        return False
    if modulo in CLINIC_MODULE and CLINIC_MODULE[modulo] not in modules.visible(request):
        return False
    if user.is_superuser:
        return True
    vinculo = getattr(request, "vinculo", None)
    if vinculo is None:
        return False
    if user.demo and modulo in READ_ONLY_IN_DEMO and acao != Action.VIEW:
        return False
    return acao in MATRIX.get(vinculo.role, {}).get(modulo, frozenset())


def own_schedule_only(request):
    """Practitioners see and change only their own schedule; the rest of the team sees all.

    "Own" means the Profissional record linked to the user (Cadastros > Profissionais).
    """
    vinculo = getattr(request, "vinculo", None)
    return (
        not request.user.is_superuser and vinculo is not None and vinculo.role == Role.PRACTITIONER
    )


def permissions_table(request):
    """All permissions as {modulo: {acao: bool}}, for use in templates."""
    return {
        modulo.value: {acao.value: can(request, modulo, acao) for acao in Action}
        for modulo in Module
    }


def requires_permission(modulo, acao):
    """View decorator: requires login, a current clinic and the given permission."""

    def decorador(view):
        @wraps(view)
        @login_required
        def protegida(request, *args, **kwargs):
            if request.clinic is None:
                if request.user.is_superuser:
                    return redirect("register_clinic")
                return render(request, "core/no_clinic.html", status=403)
            if not can(request, modulo, acao):
                raise PermissionDenied
            modules.mark_if_disabled(request, CLINIC_MODULE.get(modulo))
            return view(request, *args, **kwargs)

        return protegida

    return decorador
