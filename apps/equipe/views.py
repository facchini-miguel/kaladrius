"""Team management by the clinic administrator: members, roles and access.

Vinculo is not an isolated model, so every query here filters by the current clinic
explicitly. Accounts are never deleted (the audit log refers to them): removing
someone from the clinic means turning their access off.
"""

from django.contrib import messages
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.core.models import Vinculo
from apps.core.permissoes import Acao, Modulo, exige_permissao

from .forms import ContaForm, NovoMembroForm, SenhaForm, VinculoForm, conta_exclusiva


def _vinculo(request, pk):
    """A membership of the current clinic (404 for other clinics)."""
    return get_object_or_404(
        Vinculo.objects.select_related("usuario"), pk=pk, clinica=request.clinica
    )


@exige_permissao(Modulo.USUARIOS, Acao.VER)
def lista(request):
    em_outras_clinicas = Vinculo.objects.filter(usuario=OuterRef("usuario")).exclude(
        clinica=request.clinica
    )
    vinculos = (
        Vinculo.objects.filter(clinica=request.clinica)
        .select_related("usuario")
        .annotate(outras_clinicas=Exists(em_outras_clinicas))
        .order_by("-ativo", "usuario__first_name", "usuario__username")
    )
    return render(request, "equipe/lista.html", {"vinculos": vinculos})


@exige_permissao(Modulo.USUARIOS, Acao.CRIAR)
def novo(request):
    form = NovoMembroForm(request.POST or None, clinica=request.clinica)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            usuario = form.save()
        messages.success(
            request, _("%(nome)s agora faz parte da equipe.") % {"nome": usuario.get_full_name()}
        )
        return redirect("equipe:lista")
    return render(request, "equipe/novo.html", {"form": form})


@exige_permissao(Modulo.USUARIOS, Acao.ALTERAR)
def editar(request, pk):
    vinculo = _vinculo(request, pk)
    usuario = vinculo.usuario
    exclusiva = conta_exclusiva(usuario, request.clinica)
    dados = request.POST or None
    form = VinculoForm(dados, instance=vinculo, editor=request.user, prefix="vinculo")
    conta = ContaForm(dados, instance=usuario, prefix="conta") if exclusiva else None
    if request.method == "POST" and form.is_valid() and (conta is None or conta.is_valid()):
        with transaction.atomic():
            form.save()
            if conta is not None:
                conta.save()
        messages.success(
            request, _("Dados de %(nome)s salvos.") % {"nome": usuario.get_full_name() or usuario}
        )
        return redirect("equipe:lista")
    return render(
        request,
        "equipe/editar.html",
        {"vinculo": vinculo, "form": form, "conta": conta, "exclusiva": exclusiva},
    )


@exige_permissao(Modulo.USUARIOS, Acao.ALTERAR)
def senha(request, pk):
    vinculo = _vinculo(request, pk)
    usuario = vinculo.usuario
    if usuario == request.user:
        return redirect("trocar_senha")
    if not conta_exclusiva(usuario, request.clinica):
        messages.error(
            request,
            _(
                "%(nome)s também tem acesso a outra clínica ou à plataforma: "
                "a senha só pode ser trocada pelo próprio usuário ou pelo suporte."
            )
            % {"nome": usuario},
        )
        return redirect("equipe:editar", pk=vinculo.pk)
    form = SenhaForm(usuario, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            _("Nova senha de %(nome)s definida.") % {"nome": usuario.get_full_name() or usuario},
        )
        return redirect("equipe:lista")
    return render(request, "equipe/senha.html", {"vinculo": vinculo, "form": form})
