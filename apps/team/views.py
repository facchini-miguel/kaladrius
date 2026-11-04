"""Team management by the clinic administrator: members, roles and access.

Vinculo is not an isolated model, so every query here filters by the current clinic
explicitly. Accounts are never deleted (the audit log refers to them): removing
someone from the clinic means turning their access off.
"""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.account import services as conta_servicos
from apps.audit.models import AuditEntry
from apps.audit.record import registrar
from apps.core.models import Membership
from apps.core.permissions import Acao, Modulo, exige_permissao

from .forms import ContaForm, NovoMembroForm, SenhaForm, VinculoForm, conta_exclusiva


def _vinculo(request, pk):
    """A membership of the current clinic (404 for other clinics)."""
    return get_object_or_404(
        Membership.objects.select_related("user"), pk=pk, clinic=request.clinic
    )


@exige_permissao(Modulo.USUARIOS, Acao.VER)
def lista(request):
    vinculos = (
        Membership.objects.filter(clinic=request.clinic)
        .select_related("user")
        .order_by("-active", "user__first_name", "user__username")
    )
    return render(request, "team/list.html", {"vinculos": vinculos})


@exige_permissao(Modulo.USUARIOS, Acao.CRIAR)
def novo(request):
    form = NovoMembroForm(request.POST or None, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        messages.success(
            request, _("%(nome)s agora faz parte da equipe.") % {"nome": user.get_full_name()}
        )
        return redirect("team:list")
    return render(request, "team/new.html", {"form": form})


@exige_permissao(Modulo.USUARIOS, Acao.ALTERAR)
def editar(request, pk):
    vinculo = _vinculo(request, pk)
    user = vinculo.user
    exclusiva = conta_exclusiva(user, request.clinic)
    dados = request.POST or None
    form = VinculoForm(dados, instance=vinculo, editor=request.user, prefix="vinculo")
    account = ContaForm(dados, instance=user, prefix="conta") if exclusiva else None
    if request.method == "POST" and form.is_valid() and (account is None or account.is_valid()):
        with transaction.atomic():
            form.save()
            if account is not None:
                account.save()
        messages.success(
            request, _("Dados de %(nome)s salvos.") % {"nome": user.get_full_name() or user}
        )
        return redirect("team:list")
    return render(
        request,
        "team/edit.html",
        {
            "vinculo": vinculo,
            "form": form,
            "account": account,
            "exclusiva": exclusiva,
            "duas_etapas": conta_servicos.ativa_para(user),
        },
    )


@exige_permissao(Modulo.USUARIOS, Acao.ALTERAR)
def senha(request, pk):
    vinculo = _vinculo(request, pk)
    user = vinculo.user
    if user == request.user:
        return redirect("change_password")
    if not conta_exclusiva(user, request.clinic):
        messages.error(
            request,
            _(
                "%(nome)s também tem acesso a outra clínica ou à plataforma: "
                "a senha só pode ser trocada pelo próprio usuário ou pelo suporte."
            )
            % {"nome": user},
        )
        return redirect("team:edit", pk=vinculo.pk)
    form = SenhaForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            _("Nova senha de %(nome)s definida.") % {"nome": user.get_full_name() or user},
        )
        return redirect("team:list")
    return render(request, "team/password.html", {"vinculo": vinculo, "form": form})


@exige_permissao(Modulo.USUARIOS, Acao.ALTERAR)
def duas_etapas(request, pk):
    """Remove a member's two-step verification (lost phone, decision 111); they turn it on
    again with a new QR code."""
    vinculo = _vinculo(request, pk)
    user = vinculo.user
    if request.method == "POST" and user != request.user and conta_exclusiva(user, request.clinic):
        conta_servicos.desativar(user)
        registrar(
            AuditEntry.Acao.ALTERAR,
            user,
            description=f"{user}: verificação em duas etapas removida pelo administrador",
        )
        messages.success(
            request,
            _("Verificação em duas etapas de %(nome)s removida.")
            % {"nome": user.get_full_name() or user},
        )
    return redirect("team:edit", pk=vinculo.pk)
