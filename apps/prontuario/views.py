from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.agenda.models import Agendamento
from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.registro import registrar
from apps.pacientes.models import Paciente

from .forms import AdendoForm, AtendimentoForm, AtestadoForm, ReceitaForm
from .models import CAMPOS_DA_ANAMNESE, Atendimento, Atestado, Receita
from .permissoes import profissional_do_usuario

Acao = RegistroAuditoria.Acao
# The audit log names the changed fields but never copies clinical text (decision 081).
SIGILO = "(conteúdo clínico)"


def exige_profissional(view):
    """Only practitioners reach the medical record; the view gets their Profissional."""

    @wraps(view)
    @login_required
    def protegida(request, *args, **kwargs):
        profissional = profissional_do_usuario(request)
        if profissional is None:
            raise PermissionDenied
        return view(request, profissional, *args, **kwargs)

    return protegida


def _auditar(acao, atendimento, campos):
    if campos:
        registrar(acao, atendimento, alteracoes={campo: [SIGILO, SIGILO] for campo in campos})


def _finalizar(request, atendimento):
    atendimento.finalizado_em = timezone.now()
    atendimento.finalizado_por = request.user
    atendimento.save(update_fields=["finalizado_em", "finalizado_por", "alterado_em"])
    registrar(Acao.ALTERAR, atendimento, alteracoes={"finalizado": [None, "sim"]})
    messages.success(
        request, _("Atendimento finalizado. A partir de agora, correções são feitas por adendo.")
    )


@exige_profissional
def novo(request, profissional, paciente):
    paciente = get_object_or_404(Paciente.objects, pk=paciente, arquivado=False)
    agendamento = None
    codigo = request.POST.get("agendamento") or request.GET.get("agendamento") or ""
    if codigo.isdecimal():
        agendamento = get_object_or_404(Agendamento.objects, pk=codigo, paciente=paciente)
        existente = Atendimento.objects.filter(agendamento=agendamento).first()
        if existente is not None:
            return redirect("prontuario:atendimento", pk=existente.pk)
    inicial = {"data": agendamento.inicio if agendamento else timezone.now()}
    form = AtendimentoForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        atendimento = form.save(commit=False)
        atendimento.paciente = paciente
        atendimento.profissional = profissional
        atendimento.agendamento = agendamento
        atendimento.criado_por = request.user
        atendimento.save()
        _auditar(
            Acao.CRIAR, atendimento, [c for c in CAMPOS_DA_ANAMNESE if getattr(atendimento, c)]
        )
        if request.POST.get("acao") == "finalizar":
            _finalizar(request, atendimento)
        else:
            messages.success(request, _("Atendimento salvo."))
        return redirect("prontuario:atendimento", pk=atendimento.pk)
    return render(
        request,
        "prontuario/atendimento.html",
        {"form": form, "paciente": paciente, "agendamento": agendamento, "editavel": True},
    )


@exige_profissional
def atendimento(request, profissional, pk):
    atendimento = get_object_or_404(
        Atendimento.objects.select_related("paciente", "profissional", "agendamento"), pk=pk
    )
    # Only its author changes a visit, and only until it is finalized.
    editavel = not atendimento.finalizado and atendimento.profissional_id == profissional.pk
    form = AtendimentoForm(request.POST or None, instance=atendimento) if editavel else None
    if request.method == "POST":
        if not editavel:
            raise PermissionDenied
        if form.is_valid():
            alterados = list(form.changed_data)
            form.save()
            _auditar(Acao.ALTERAR, atendimento, alterados)
            if request.POST.get("acao") == "finalizar":
                _finalizar(request, atendimento)
            else:
                messages.success(request, _("Atendimento salvo."))
            return redirect("prontuario:atendimento", pk=atendimento.pk)
    else:
        registrar(Acao.VISUALIZAR, atendimento)
    return render(
        request,
        "prontuario/atendimento.html",
        {
            "atendimento": atendimento,
            "paciente": atendimento.paciente,
            "agendamento": atendimento.agendamento,
            "form": form,
            "editavel": editavel,
            "campos": _campos(atendimento),
            "adendos": atendimento.adendos.select_related("profissional"),
            "adendo_form": AdendoForm() if atendimento.finalizado else None,
            # Certificates and prescriptions are issued by the visit's author (decision 082).
            "emite_documentos": atendimento.profissional_id == profissional.pk,
            "atestados": atendimento.atestados.all(),
            "receitas": atendimento.receitas.all(),
        },
    )


def _campos(atendimento):
    return [
        (atendimento._meta.get_field(campo).verbose_name, getattr(atendimento, campo))
        for campo in CAMPOS_DA_ANAMNESE
    ]


def _do_autor(profissional, pk):
    atendimento = get_object_or_404(Atendimento.objects.select_related("paciente"), pk=pk)
    if atendimento.profissional_id != profissional.pk:
        raise PermissionDenied
    return atendimento


@exige_profissional
def imprimir(request, profissional, pk):
    """The finalized visit, ready to print and sign (without a digital signature, the
    printed and signed copy is the legal record)."""
    atendimento = get_object_or_404(
        Atendimento.objects.select_related("paciente", "profissional"), pk=pk
    )
    if not atendimento.finalizado:
        raise PermissionDenied
    registrar(Acao.VISUALIZAR, atendimento, descricao=f"{atendimento} (impressão)")
    return render(
        request,
        "prontuario/imprimir.html",
        {
            "atendimento": atendimento,
            "campos": _campos(atendimento),
            "adendos": atendimento.adendos.select_related("profissional"),
        },
    )


@exige_profissional
def atestado_novo(request, profissional, pk):
    atendimento = _do_autor(profissional, pk)
    agendamento = atendimento.agendamento
    momento = timezone.localtime(agendamento.inicio if agendamento else atendimento.data)
    inicial = {
        "data": momento.date(),
        "hora_inicio": momento.time().replace(second=0, microsecond=0),
        "hora_fim": timezone.localtime(agendamento.fim).time() if agendamento else None,
    }
    form = AtestadoForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        atestado = form.save(commit=False)
        atestado.atendimento = atendimento
        atestado.profissional = profissional
        atestado.criado_por = request.user
        atestado.save()
        registrar(
            Acao.CRIAR,
            atestado,
            alteracoes={
                "tipo": [None, atestado.tipo],
                "dias": [None, atestado.dias],
                **({"observacao": [None, SIGILO]} if atestado.observacao else {}),
            },
        )
        messages.success(request, _("Atestado emitido."))
        return redirect("prontuario:atestado", pk=atestado.pk)
    return render(
        request,
        "prontuario/documento_form.html",
        {"form": form, "atendimento": atendimento, "titulo": _("Emitir atestado")},
    )


@exige_profissional
def receita_nova(request, profissional, pk):
    atendimento = _do_autor(profissional, pk)
    form = ReceitaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        receita = form.save(commit=False)
        receita.atendimento = atendimento
        receita.profissional = profissional
        receita.criado_por = request.user
        receita.save()
        registrar(Acao.CRIAR, receita, alteracoes={"prescricao": [None, SIGILO]})
        messages.success(request, _("Receita emitida."))
        return redirect("prontuario:receita", pk=receita.pk)
    return render(
        request,
        "prontuario/documento_form.html",
        {"form": form, "atendimento": atendimento, "titulo": _("Emitir receita")},
    )


@exige_profissional
def atestado(request, profissional, pk):
    atestado = get_object_or_404(
        Atestado.objects.select_related("atendimento__paciente", "profissional"), pk=pk
    )
    registrar(Acao.VISUALIZAR, atestado)
    return render(request, "prontuario/atestado.html", {"atestado": atestado})


@exige_profissional
def receita(request, profissional, pk):
    receita = get_object_or_404(
        Receita.objects.select_related("atendimento__paciente", "profissional"), pk=pk
    )
    registrar(Acao.VISUALIZAR, receita)
    linhas = [linha for linha in receita.prescricao.splitlines() if linha.strip()]
    return render(request, "prontuario/receita.html", {"receita": receita, "linhas": linhas})


@require_POST
@exige_profissional
def adendo(request, profissional, pk):
    atendimento = get_object_or_404(Atendimento.objects, pk=pk)
    if not atendimento.finalizado:
        raise PermissionDenied  # before finalizing, the author simply edits the visit
    form = AdendoForm(request.POST)
    if form.is_valid():
        adendo = form.save(commit=False)
        adendo.atendimento = atendimento
        adendo.profissional = profissional
        adendo.criado_por = request.user
        adendo.save()
        registrar(Acao.CRIAR, adendo, alteracoes={"texto": [None, SIGILO]})
        messages.success(request, _("Adendo incluído."))
    else:
        messages.error(request, _("Escreva o adendo."))
    return redirect("prontuario:atendimento", pk=atendimento.pk)
