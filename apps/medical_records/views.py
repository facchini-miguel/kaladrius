from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.audit.models import AuditEntry
from apps.audit.record import registrar
from apps.core import modules
from apps.core.models import ModuloClinico
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.schedule.models import Appointment

from .forms import (
    AdendoForm,
    AnexoForm,
    AtendimentoForm,
    AtestadoForm,
    PedidoDeExamesForm,
    ReceitaForm,
)
from .models import CAMPOS_DA_ANAMNESE, Attachment, Certificate, ExamRequest, Prescription, Visit
from .permissions import acessa_prontuario, administra_prontuario, profissional_do_usuario

Acao = AuditEntry.Acao
# The audit log names the changed fields but never copies clinical text (decision 081).
SIGILO = "(conteúdo clínico)"


def exige_profissional(view):
    """Only practitioners and the system administrator reach the medical record; the view
    gets the user's Profissional (None for a system administrator who is not one)."""

    @wraps(view)
    @login_required
    def protegida(request, *args, **kwargs):
        if not acessa_prontuario(request):
            raise PermissionDenied
        modules.marcar_se_desligado(request, ModuloClinico.PRONTUARIO)
        return view(request, profissional_do_usuario(request), *args, **kwargs)

    return protegida


def _auditar(acao, atendimento, campos):
    if campos:
        registrar(acao, atendimento, alteracoes={campo: [SIGILO, SIGILO] for campo in campos})


def _finalizar(request, atendimento):
    atendimento.finalizado_em = timezone.now()
    atendimento.finalizado_por = request.user
    atendimento.save(update_fields=["finalizado_em", "finalizado_por", "updated_at"])
    registrar(Acao.ALTERAR, atendimento, alteracoes={"finalizado": [None, "sim"]})
    messages.success(
        request, _("Atendimento finalizado. A partir de agora, correções são feitas por adendo.")
    )


@exige_profissional
def novo(request, practitioner, patient):
    patient = get_object_or_404(Patient.objects, pk=patient, arquivado=False)
    agendamento = None
    code = request.POST.get("agendamento") or request.GET.get("agendamento") or ""
    if code.isdecimal():
        agendamento = get_object_or_404(Appointment.objects, pk=code, patient=patient)
        existente = Visit.objects.filter(agendamento=agendamento).first()
        if existente is not None:
            return redirect("medical_records:visit", pk=existente.pk)
    inicial = {"data": agendamento.inicio if agendamento else timezone.now()}
    profissionais = None
    if administra_prontuario(request):
        profissionais = Practitioner.objects.filter(active=True)
        inicial["practitioner"] = agendamento.practitioner if agendamento else practitioner
    form = AtendimentoForm(request.POST or None, initial=inicial, profissionais=profissionais)
    if request.method == "POST" and form.is_valid():
        atendimento = form.save(commit=False)
        atendimento.patient = patient
        atendimento.practitioner = form.cleaned_data.get("practitioner") or practitioner
        atendimento.agendamento = agendamento
        atendimento.created_by = request.user
        atendimento.save()
        _auditar(
            Acao.CRIAR, atendimento, [c for c in CAMPOS_DA_ANAMNESE if getattr(atendimento, c)]
        )
        if request.POST.get("acao") == "finalizar":
            _finalizar(request, atendimento)
        else:
            messages.success(request, _("Atendimento salvo."))
        return redirect("medical_records:visit", pk=atendimento.pk)
    return render(
        request,
        "medical_records/visit.html",
        {"form": form, "patient": patient, "agendamento": agendamento, "editavel": True},
    )


@exige_profissional
def atendimento(request, practitioner, pk):
    atendimento = get_object_or_404(
        Visit.objects.select_related("patient", "practitioner", "agendamento"), pk=pk
    )
    # Only its author (or the system administrator) changes a visit, until it is finalized.
    administra = administra_prontuario(request)
    do_autor = practitioner is not None and atendimento.practitioner_id == practitioner.pk
    editavel = not atendimento.finalizado and (do_autor or administra)
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
            return redirect("medical_records:visit", pk=atendimento.pk)
    else:
        registrar(Acao.VISUALIZAR, atendimento)
    return render(
        request,
        "medical_records/visit.html",
        {
            "atendimento": atendimento,
            "patient": atendimento.patient,
            "agendamento": atendimento.agendamento,
            "form": form,
            "editavel": editavel,
            "campos": _campos(atendimento),
            "adendos": atendimento.adendos.select_related("practitioner"),
            "adendo_form": AdendoForm() if atendimento.finalizado else None,
            # Certificates and prescriptions are issued by the visit's author (decision 082).
            "emite_documentos": do_autor or administra,
            "administra": administra,
            "atestados": atendimento.atestados.all(),
            "receitas": atendimento.receitas.all(),
            "pedidos": atendimento.pedidos_de_exames.all(),
            # Never the file contents in a list.
            "anexos": atendimento.anexos.defer("conteudo").select_related("practitioner"),
            "anexo_form": AnexoForm(),
            "remove_anexos": not atendimento.finalizado,
        },
    )


def _campos(atendimento):
    return [
        (atendimento._meta.get_field(campo).verbose_name, getattr(atendimento, campo))
        for campo in CAMPOS_DA_ANAMNESE
    ]


def _do_autor(request, practitioner, pk):
    """The visit, if the user is its author or the system administrator."""
    atendimento = get_object_or_404(Visit.objects.select_related("patient"), pk=pk)
    do_autor = practitioner is not None and atendimento.practitioner_id == practitioner.pk
    if not (do_autor or administra_prontuario(request)):
        raise PermissionDenied
    return atendimento


@exige_profissional
def imprimir(request, practitioner, pk):
    """The finalized visit, ready to print and sign (without a digital signature, the
    printed and signed copy is the legal record)."""
    atendimento = get_object_or_404(Visit.objects.select_related("patient", "practitioner"), pk=pk)
    if not atendimento.finalizado:
        raise PermissionDenied
    registrar(Acao.VISUALIZAR, atendimento, description=f"{atendimento} (impressão)")
    return render(
        request,
        "medical_records/print.html",
        {
            "atendimento": atendimento,
            "campos": _campos(atendimento),
            "adendos": atendimento.adendos.select_related("practitioner"),
        },
    )


@exige_profissional
def atestado_novo(request, practitioner, pk):
    atendimento = _do_autor(request, practitioner, pk)
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
        atestado.practitioner = atendimento.practitioner
        atestado.created_by = request.user
        atestado.save()
        registrar(
            Acao.CRIAR,
            atestado,
            alteracoes={
                "tipo": [None, atestado.tipo],
                "dias": [None, atestado.dias],
                **({"note": [None, SIGILO]} if atestado.note else {}),
            },
        )
        messages.success(request, _("Atestado emitido."))
        return redirect("medical_records:certificate", pk=atestado.pk)
    return render(
        request,
        "medical_records/document_form.html",
        {"form": form, "atendimento": atendimento, "titulo": _("Emitir atestado")},
    )


@exige_profissional
def receita_nova(request, practitioner, pk):
    atendimento = _do_autor(request, practitioner, pk)
    form = ReceitaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        receita = form.save(commit=False)
        receita.atendimento = atendimento
        receita.practitioner = atendimento.practitioner
        receita.created_by = request.user
        receita.save()
        registrar(Acao.CRIAR, receita, alteracoes={"prescricao": [None, SIGILO]})
        messages.success(request, _("Receita emitida."))
        return redirect("medical_records:prescription", pk=receita.pk)
    return render(
        request,
        "medical_records/document_form.html",
        {"form": form, "atendimento": atendimento, "titulo": _("Emitir receita")},
    )


@exige_profissional
def atestado(request, practitioner, pk):
    atestado = get_object_or_404(
        Certificate.objects.select_related("atendimento__patient", "practitioner"), pk=pk
    )
    registrar(Acao.VISUALIZAR, atestado)
    return render(request, "medical_records/certificate.html", {"atestado": atestado})


@exige_profissional
def receita(request, practitioner, pk):
    receita = get_object_or_404(
        Prescription.objects.select_related("atendimento__patient", "practitioner"), pk=pk
    )
    registrar(Acao.VISUALIZAR, receita)
    linhas = [linha for linha in receita.prescricao.splitlines() if linha.strip()]
    return render(
        request, "medical_records/prescription.html", {"receita": receita, "linhas": linhas}
    )


@require_POST
@exige_profissional
def adendo(request, practitioner, pk):
    atendimento = get_object_or_404(Visit.objects, pk=pk)
    if not atendimento.finalizado:
        raise PermissionDenied  # before finalizing, the author simply edits the visit
    form = AdendoForm(request.POST)
    if form.is_valid():
        adendo = form.save(commit=False)
        adendo.atendimento = atendimento
        adendo.practitioner = practitioner or atendimento.practitioner
        adendo.created_by = request.user
        adendo.save()
        registrar(Acao.CRIAR, adendo, alteracoes={"texto": [None, SIGILO]})
        messages.success(request, _("Adendo incluído."))
    else:
        messages.error(request, _("Escreva o adendo."))
    return redirect("medical_records:visit", pk=atendimento.pk)


@exige_profissional
def pedido_de_exames_novo(request, practitioner, pk):
    atendimento = _do_autor(request, practitioner, pk)
    form = PedidoDeExamesForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pedido = form.save(commit=False)
        pedido.atendimento = atendimento
        pedido.practitioner = atendimento.practitioner
        pedido.created_by = request.user
        pedido.save()
        registrar(
            Acao.CRIAR,
            pedido,
            alteracoes={
                "exames": [None, SIGILO],
                **({"indicacao": [None, SIGILO]} if pedido.indicacao else {}),
            },
        )
        messages.success(request, _("Pedido de exames emitido."))
        return redirect("medical_records:exam_request", pk=pedido.pk)
    return render(
        request,
        "medical_records/document_form.html",
        {"form": form, "atendimento": atendimento, "titulo": _("Pedir exames")},
    )


@exige_profissional
def pedido_de_exames(request, practitioner, pk):
    pedido = get_object_or_404(
        ExamRequest.objects.select_related("atendimento__patient", "practitioner"), pk=pk
    )
    registrar(Acao.VISUALIZAR, pedido)
    linhas = [linha for linha in pedido.exames.splitlines() if linha.strip()]
    return render(
        request, "medical_records/exam_request.html", {"pedido": pedido, "linhas": linhas}
    )


@require_POST
@exige_profissional
def anexo_enviar(request, practitioner, pk):
    """Any practitioner adds files to a visit, even a finalized one (results arrive later)."""
    atendimento = get_object_or_404(Visit.objects, pk=pk)
    if request.user.demonstracao:
        messages.error(request, _("Contas de demonstração não enviam anexos."))
        return redirect("medical_records:visit", pk=atendimento.pk)
    form = AnexoForm(request.POST, request.FILES)
    if form.is_valid():
        arquivo = form.cleaned_data["arquivo"]
        anexo = Attachment.objects.create(
            atendimento=atendimento,
            description=form.cleaned_data["description"],
            name=arquivo.name[:255],
            tipo=arquivo.tipo_conferido,
            tamanho=arquivo.size,
            conteudo=arquivo.read(),
            practitioner=practitioner or atendimento.practitioner,
            created_by=request.user,
        )
        registrar(
            Acao.CRIAR,
            anexo,
            description=f"{atendimento} – {_('anexo')}",
            alteracoes={"arquivo": [None, SIGILO]},
        )
        messages.success(request, _("Anexo incluído."))
    else:
        messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
    return redirect("medical_records:visit", pk=atendimento.pk)


@exige_profissional
def anexo(request, practitioner, pk):
    anexo = get_object_or_404(Attachment.objects.select_related("atendimento"), pk=pk)
    registrar(Acao.VISUALIZAR, anexo, description=f"{anexo.atendimento} – {_('anexo')}")
    resposta = HttpResponse(bytes(anexo.conteudo), content_type=anexo.tipo)
    # Opened in the browser (only PDF, JPG and PNG are ever stored), never cached.
    name = "".join(c for c in anexo.name if c.isalnum() or c in "._- ") or "anexo"
    resposta["Content-Disposition"] = f'inline; filename="{name}"'
    resposta["Cache-Control"] = "private, no-store"
    return resposta


@require_POST
@exige_profissional
def anexo_remover(request, practitioner, pk):
    """Who sent a file (or the system administrator) removes it while the visit is still a
    draft; afterwards it stays."""
    anexo = get_object_or_404(
        Attachment.objects.select_related("atendimento").defer("conteudo"), pk=pk
    )
    quem_enviou = anexo.created_by_id == request.user.pk
    if anexo.atendimento.finalizado or not (quem_enviou or administra_prontuario(request)):
        raise PermissionDenied
    atendimento = anexo.atendimento
    registrar(
        Acao.EXCLUIR,
        anexo,
        description=f"{atendimento} – {_('anexo')}",
        alteracoes={"arquivo": [SIGILO, None]},
    )
    anexo.delete()
    messages.success(request, _("Anexo removido."))
    return redirect("medical_records:visit", pk=atendimento.pk)
