"""Role-based permissions per clinic.

Each role (Papel) gets a set of actions (Acao) per module (Modulo). The same check
guards the views (server side) and decides which menus and buttons the templates show.
Platform superusers can do everything in any clinic.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _

from .models import Papel


class Modulo(models.TextChoices):
    PACIENTES = "pacientes", _("Pacientes")
    AGENDA = "agenda", _("Agenda")
    RECHAMADAS = "rechamadas", _("Rechamadas")
    ANIVERSARIANTES = "aniversariantes", _("Aniversariantes")
    PROFISSIONAIS = "profissionais", _("Profissionais")
    CADASTROS = "cadastros", _("Tabelas base")
    USUARIOS = "usuarios", _("Usuários da clínica")
    CLINICA = "clinica", _("Configurações da clínica")
    AUDITORIA = "auditoria", _("Auditoria")
    # Receivables, receiving payments, receipts and debtors (front desk included).
    RECEBIMENTOS = "recebimentos", _("Recebimentos")
    # Accounts, categories and (0.16) payables and cash flow: administrators only.
    FINANCEIRO = "financeiro", _("Financeiro")
    # Treatment estimates (0.18.0): written by practitioners and the front desk.
    ORCAMENTOS = "orcamentos", _("Orçamentos")


class Acao(models.TextChoices):
    VER = "ver", _("Ver")
    CRIAR = "criar", _("Criar")
    ALTERAR = "alterar", _("Alterar")
    EXCLUIR = "excluir", _("Excluir")


_TODAS = frozenset(Acao)
_VER = frozenset({Acao.VER})
_SEM_EXCLUIR = frozenset({Acao.VER, Acao.CRIAR, Acao.ALTERAR})

# Default permission matrix. To be reviewed with the owner after phase 1.
MATRIZ = {
    Papel.ADMIN: {modulo: _TODAS for modulo in Modulo},
    Papel.RECEPCAO: {
        Modulo.PACIENTES: _SEM_EXCLUIR,
        Modulo.AGENDA: _TODAS,
        Modulo.RECHAMADAS: _TODAS,
        Modulo.ANIVERSARIANTES: _VER,
        Modulo.PROFISSIONAIS: _VER,
        Modulo.CADASTROS: _VER,
        # Cancelling entries, reversing payments and discounts stay with administrators.
        Modulo.RECEBIMENTOS: _SEM_EXCLUIR,
        Modulo.ORCAMENTOS: _SEM_EXCLUIR,
    },
    Papel.PROFISSIONAL: {
        Modulo.PACIENTES: _SEM_EXCLUIR,
        Modulo.AGENDA: _SEM_EXCLUIR,
        Modulo.RECHAMADAS: _SEM_EXCLUIR,
        Modulo.ANIVERSARIANTES: _VER,
        Modulo.PROFISSIONAIS: _VER,
        Modulo.CADASTROS: _VER,
        Modulo.ORCAMENTOS: _SEM_EXCLUIR,
    },
}


def pode(request, modulo, acao):
    """Whether the current user may perform `acao` on `modulo` in the current clinic."""
    usuario = request.user
    if not usuario.is_authenticated or getattr(request, "clinica", None) is None:
        return False
    if usuario.is_superuser:
        return True
    vinculo = getattr(request, "vinculo", None)
    if vinculo is None:
        return False
    return acao in MATRIZ.get(vinculo.papel, {}).get(modulo, frozenset())


def so_a_propria_agenda(request):
    """Practitioners see and change only their own schedule; the rest of the team sees all.

    "Own" means the Profissional record linked to the user (Cadastros > Profissionais).
    """
    vinculo = getattr(request, "vinculo", None)
    return (
        not request.user.is_superuser
        and vinculo is not None
        and vinculo.papel == Papel.PROFISSIONAL
    )


def tabela_permissoes(request):
    """All permissions as {modulo: {acao: bool}}, for use in templates."""
    return {
        modulo.value: {acao.value: pode(request, modulo, acao) for acao in Acao}
        for modulo in Modulo
    }


def exige_permissao(modulo, acao):
    """View decorator: requires login, a current clinic and the given permission."""

    def decorador(view):
        @wraps(view)
        @login_required
        def protegida(request, *args, **kwargs):
            if request.clinica is None:
                if request.user.is_superuser:
                    destino = reverse("trocar_clinica")
                    return redirect(f"{destino}?{urlencode({'next': request.get_full_path()})}")
                return render(request, "core/sem_clinica.html", status=403)
            if not pode(request, modulo, acao):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return protegida

    return decorador
