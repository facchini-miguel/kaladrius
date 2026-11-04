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


def _auditar(acao, visit, campos):
    if campos:
        registrar(acao, visit, alteracoes={campo: [SIGILO, SIGILO] for campo in campos})


def _finalizar(request, visit):
    visit.finalizado_em = timezone.now()
    visit.finalizado_por = request.user
    visit.save(update_fields=["finalizado_em", "finalizado_por", "updated_at"])
    registrar(Acao.ALTERAR, visit, alteracoes={"finalizado": [None, "sim"]})
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
    inicial = {"date": agendamento.start if agendamento else timezone.now()}
    profissionais = None
    if administra_prontuario(request):
        profissionais = Practitioner.objects.filter(active=True)
        inicial["practitioner"] = agendamento.practitioner if agendamento else practitioner
    form = AtendimentoForm(request.POST or None, initial=inicial, profissionais=profissionais)
    if request.method == "POST" and form.is_valid():
        visit = form.save(commit=False)
        visit.patient = patient
        visit.practitioner = form.cleaned_data.get("practitioner") or practitioner
        visit.agendamento = agendamento
        visit.created_by = request.user
        visit.save()
        _auditar(Acao.CRIAR, visit, [c for c in CAMPOS_DA_ANAMNESE if getattr(visit, c)])
        if request.POST.get("acao") == "finalizar":
            _finalizar(request, visit)
        else:
            messages.success(request, _("Atendimento salvo."))
        return redirect("medical_records:visit", pk=visit.pk)
    return render(
        request,
        "medical_records/visit.html",
        {"form": form, "patient": patient, "agendamento": agendamento, "editavel": True},
    )


@exige_profissional
def visit(request, practitioner, pk):
    visit = get_object_or_404(
        Visit.objects.select_related("patient", "practitioner", "agendamento"), pk=pk
    )
    # Only its author (or the system administrator) changes a visit, until it is finalized.
    administra = administra_prontuario(request)
    do_autor = practitioner is not None and visit.practitioner_id == practitioner.pk
    editavel = not visit.finalizado and (do_autor or administra)
    form = AtendimentoForm(request.POST or None, instance=visit) if editavel else None
    if request.method == "POST":
        if not editavel:
            raise PermissionDenied
        if form.is_valid():
            alterados = list(form.changed_data)
            form.save()
            _auditar(Acao.ALTERAR, visit, alterados)
            if request.POST.get("acao") == "finalizar":
                _finalizar(request, visit)
            else:
                messages.success(request, _("Atendimento salvo."))
            return redirect("medical_records:visit", pk=visit.pk)
    else:
        registrar(Acao.VISUALIZAR, visit)
    return render(
        request,
        "medical_records/visit.html",
        {
            "visit": visit,
            "patient": visit.patient,
            "agendamento": visit.agendamento,
            "form": form,
            "editavel": editavel,
            "campos": _campos(visit),
            "adendos": visit.adendos.select_related("practitioner"),
            "adendo_form": AdendoForm() if visit.finalizado else None,
            # Certificates and prescriptions are issued by the visit's author (decision 082).
            "emite_documentos": do_autor or administra,
            "administra": administra,
            "atestados": visit.atestados.all(),
            "receitas": visit.receitas.all(),
            "pedidos": visit.pedidos_de_exames.all(),
            # Never the file contents in a list.
            "anexos": visit.anexos.defer("conteudo").select_related("practitioner"),
            "anexo_form": AnexoForm(),
            "remove_anexos": not visit.finalizado,
        },
    )


def _campos(visit):
    return [
        (visit._meta.get_field(campo).verbose_name, getattr(visit, campo))
        for campo in CAMPOS_DA_ANAMNESE
    ]


def _do_autor(request, practitioner, pk):
    """The visit, if the user is its author or the system administrator."""
    visit = get_object_or_404(Visit.objects.select_related("patient"), pk=pk)
    do_autor = practitioner is not None and visit.practitioner_id == practitioner.pk
    if not (do_autor or administra_prontuario(request)):
        raise PermissionDenied
    return visit


@exige_profissional
def imprimir(request, practitioner, pk):
    """The finalized visit, ready to print and sign (without a digital signature, the
    printed and signed copy is the legal record)."""
    visit = get_object_or_404(Visit.objects.select_related("patient", "practitioner"), pk=pk)
    if not visit.finalizado:
        raise PermissionDenied
    registrar(Acao.VISUALIZAR, visit, description=f"{visit} (impressão)")
    return render(
        request,
        "medical_records/print.html",
        {
            "visit": visit,
            "campos": _campos(visit),
            "adendos": visit.adendos.select_related("practitioner"),
        },
    )


@exige_profissional
def atestado_novo(request, practitioner, pk):
    visit = _do_autor(request, practitioner, pk)
    agendamento = visit.agendamento
    timestamp = timezone.localtime(agendamento.start if agendamento else visit.date)
    inicial = {
        "date": timestamp.date(),
        "hora_inicio": timestamp.time().replace(second=0, microsecond=0),
        "hora_fim": timezone.localtime(agendamento.end).time() if agendamento else None,
    }
    form = AtestadoForm(request.POST or None, initial=inicial)
    if request.method == "POST" and form.is_valid():
        atestado = form.save(commit=False)
        atestado.visit = visit
        atestado.practitioner = visit.practitioner
        atestado.created_by = request.user
        atestado.save()
        registrar(
            Acao.CRIAR,
            atestado,
            alteracoes={
                "kind": [None, atestado.kind],
                "dias": [None, atestado.dias],
                **({"note": [None, SIGILO]} if atestado.note else {}),
            },
        )
        messages.success(request, _("Atestado emitido."))
        return redirect("medical_records:certificate", pk=atestado.pk)
    return render(
        request,
        "medical_records/document_form.html",
        {"form": form, "visit": visit, "titulo": _("Emitir atestado")},
    )


@exige_profissional
def receita_nova(request, practitioner, pk):
    visit = _do_autor(request, practitioner, pk)
    form = ReceitaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        receita = form.save(commit=False)
        receita.visit = visit
        receita.practitioner = visit.practitioner
        receita.created_by = request.user
        receita.save()
        registrar(Acao.CRIAR, receita, alteracoes={"prescricao": [None, SIGILO]})
        messages.success(request, _("Receita emitida."))
        return redirect("medical_records:prescription", pk=receita.pk)
    return render(
        request,
        "medical_records/document_form.html",
        {"form": form, "visit": visit, "titulo": _("Emitir receita")},
    )


@exige_profissional
def atestado(request, practitioner, pk):
    atestado = get_object_or_404(
        Certificate.objects.select_related("visit__patient", "practitioner"), pk=pk
    )
    registrar(Acao.VISUALIZAR, atestado)
    return render(request, "medical_records/certificate.html", {"atestado": atestado})


@exige_profissional
def receita(request, practitioner, pk):
    receita = get_object_or_404(
        Prescription.objects.select_related("visit__patient", "practitioner"), pk=pk
    )
    registrar(Acao.VISUALIZAR, receita)
    linhas = [linha for linha in receita.prescricao.splitlines() if linha.strip()]
    return render(
        request, "medical_records/prescription.html", {"receita": receita, "linhas": linhas}
    )


@require_POST
@exige_profissional
def adendo(request, practitioner, pk):
    visit = get_object_or_404(Visit.objects, pk=pk)
    if not visit.finalizado:
        raise PermissionDenied  # before finalizing, the author simply edits the visit
    form = AdendoForm(request.POST)
    if form.is_valid():
        adendo = form.save(commit=False)
        adendo.visit = visit
        adendo.practitioner = practitioner or visit.practitioner
        adendo.created_by = request.user
        adendo.save()
        registrar(Acao.CRIAR, adendo, alteracoes={"texto": [None, SIGILO]})
        messages.success(request, _("Adendo incluído."))
    else:
        messages.error(request, _("Escreva o adendo."))
    return redirect("medical_records:visit", pk=visit.pk)


@exige_profissional
def pedido_de_exames_novo(request, practitioner, pk):
    visit = _do_autor(request, practitioner, pk)
    form = PedidoDeExamesForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pedido = form.save(commit=False)
        pedido.visit = visit
        pedido.practitioner = visit.practitioner
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
        {"form": form, "visit": visit, "titulo": _("Pedir exames")},
    )


@exige_profissional
def pedido_de_exames(request, practitioner, pk):
    pedido = get_object_or_404(
        ExamRequest.objects.select_related("visit__patient", "practitioner"), pk=pk
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
    visit = get_object_or_404(Visit.objects, pk=pk)
    if request.user.demonstracao:
        messages.error(request, _("Contas de demonstração não enviam anexos."))
        return redirect("medical_records:visit", pk=visit.pk)
    form = AnexoForm(request.POST, request.FILES)
    if form.is_valid():
        file = form.cleaned_data["file"]
        anexo = Attachment.objects.create(
            visit=visit,
            description=form.cleaned_data["description"],
            name=file.name[:255],
            kind=file.tipo_conferido,
            size=file.size,
            conteudo=file.read(),
            practitioner=practitioner or visit.practitioner,
            created_by=request.user,
        )
        registrar(
            Acao.CRIAR,
            anexo,
            description=f"{visit} – {_('anexo')}",
            alteracoes={"file": [None, SIGILO]},
        )
        messages.success(request, _("Anexo incluído."))
    else:
        messages.error(request, " ".join(e for erros in form.errors.values() for e in erros))
    return redirect("medical_records:visit", pk=visit.pk)


@exige_profissional
def anexo(request, practitioner, pk):
    anexo = get_object_or_404(Attachment.objects.select_related("visit"), pk=pk)
    registrar(Acao.VISUALIZAR, anexo, description=f"{anexo.visit} – {_('anexo')}")
    resposta = HttpResponse(bytes(anexo.conteudo), content_type=anexo.kind)
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
    anexo = get_object_or_404(Attachment.objects.select_related("visit").defer("conteudo"), pk=pk)
    quem_enviou = anexo.created_by_id == request.user.pk
    if anexo.visit.finalizado or not (quem_enviou or administra_prontuario(request)):
        raise PermissionDenied
    visit = anexo.visit
    registrar(
        Acao.EXCLUIR,
        anexo,
        description=f"{visit} – {_('anexo')}",
        alteracoes={"file": [SIGILO, None]},
    )
    anexo.delete()
    messages.success(request, _("Anexo removido."))
    return redirect("medical_records:visit", pk=visit.pk)
