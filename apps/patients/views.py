from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dates import MONTHS
from django.utils.http import urlencode
from django.utils.translation import gettext as _

from apps.audit.models import AuditEntry
from apps.audit.record import anonimizar, registrar
from apps.core import legislation
from apps.core.permissions import Acao, Modulo, exige_permissao, pode
from apps.core.validators import normalizar_cnpj
from apps.estimates.models import Estimate, EstimateItem
from apps.finance.models import Entry, Installment, Payment
from apps.finance.services import resumo_do_paciente
from apps.health_plans.models import MemberCard
from apps.medical_records.models import Visit
from apps.medical_records.permissions import acessa_prontuario
from apps.recalls.models import Recall
from apps.schedule.models import Appointment
from apps.schedule.services import agendamentos_visiveis

from .forms import PacienteForm, PessoaRelacionadaForm
from .models import Patient, RelatedPerson

POR_PAGINA = 50
SITUACOES = {
    "ativos": Q(active=True, arquivado=False),
    "inativos": Q(active=False, arquivado=False),
    "todos": Q(arquivado=False),
    "arquivados": Q(arquivado=True),  # clinic administrators only (see lista)
}


def _ve_arquivados(request):
    """Archived patients are seen (and restored or deleted) only by who could delete."""
    return pode(request, Modulo.PACIENTES, Acao.EXCLUIR)


def _visiveis(request):
    if _ve_arquivados(request):
        return Patient.objects.all()
    return Patient.objects.filter(arquivado=False)


def filtrar(pacientes, busca, kind, status):
    """Search by name/company name (accent-insensitive), CPF/CNPJ prefix or patient code."""
    if busca:
        filtro = Q(name__unaccent__icontains=busca) | Q(razao_social__unaccent__icontains=busca)
        documento = normalizar_cnpj(busca)
        if len(documento) >= 3 and not any(c.isspace() for c in busca.strip()):
            filtro |= Q(cpf_cnpj__startswith=documento)
        if busca.isdecimal() and len(busca) <= 9:
            filtro |= Q(pk=int(busca))
        pacientes = pacientes.filter(filtro)
    if kind in Patient.Tipo.values:
        pacientes = pacientes.filter(kind=kind)
    return pacientes.filter(SITUACOES.get(status, SITUACOES["ativos"]))


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def lista(request):
    busca = request.GET.get("q", "").strip()
    kind = request.GET.get("kind", "")
    status = request.GET.get("status", "ativos")
    if status == "arquivados" and not _ve_arquivados(request):
        status = "ativos"
    pacientes = filtrar(Patient.objects.select_related("cidade__uf"), busca, kind, status)
    pagina = Paginator(pacientes, POR_PAGINA).get_page(request.GET.get("pagina"))
    return render(
        request,
        "patients/list.html",
        {
            "pagina": pagina,
            "busca": busca,
            "kind": kind,
            "status": status,
            "tipos": Patient.Tipo.choices,
            "parametros": urlencode({"q": busca, "kind": kind, "status": status}),
        },
    )


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def ficha(request, pk):
    patient = get_object_or_404(
        _visiveis(request).select_related("cidade__uf", "estado_civil", "arquivado_por"), pk=pk
    )
    # LGPD: access to a patient's record (health data) is logged.
    registrar(AuditEntry.Acao.VISUALIZAR, patient)
    rechamadas = Recall.objects.filter(patient=patient).order_by("-date")[:20]
    contexto = {"patient": patient, "rechamadas": rechamadas}
    if pode(request, Modulo.AGENDA, Acao.VER):
        contexto["agendamentos"] = _historico(request, patient)
    if pode(request, Modulo.RECEBIMENTOS, Acao.VER):
        contexto["financeiro"] = resumo_do_paciente(patient)
    if pode(request, Modulo.ORCAMENTOS, Acao.VER):
        contexto["orcamentos"] = list(
            Estimate.objects.filter(patient=patient).prefetch_related("itens")[:10]
        )
    if pode(request, Modulo.CONVENIOS, Acao.VER):
        contexto["carteirinhas"] = list(
            MemberCard.objects.filter(patient=patient).select_related("convenio")
        )
    contexto["relacionados"] = relacionados_de(patient)
    if acessa_prontuario(request):
        contexto["prontuario"] = list(
            Visit.objects.filter(patient=patient).select_related("practitioner")
        )
    return render(request, "patients/record.html", contexto)


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def imprimir(request, pk):
    """The registration sheet, ready to print or save as PDF (as the legacy Medical's
    fichapaciente_imp): identification, contact, address and health plan cards."""
    patient = get_object_or_404(
        _visiveis(request).select_related("cidade__uf", "estado_civil"), pk=pk
    )
    registrar(AuditEntry.Acao.VISUALIZAR, patient)  # LGPD, as the record
    carteirinhas = (
        list(MemberCard.objects.filter(patient=patient, active=True).select_related("convenio"))
        if pode(request, Modulo.CONVENIOS, Acao.VER)
        else None
    )
    return render(
        request,
        "patients/print.html",
        {
            "patient": patient,
            "carteirinhas": carteirinhas,
            "relacionados": RelatedPerson.objects.filter(patient=patient).select_related(
                "outro_paciente"
            ),
            "hoje": timezone.localdate(),
        },
    )


HISTORICO = 10  # appointments shown in each list of the patient record


def _historico(request, patient):
    """The patient's next and latest appointments (practitioners: only their own)."""
    deste = (
        agendamentos_visiveis(request)
        .filter(patient=patient)
        .select_related("practitioner", "kind")
    )
    agora = timezone.now()
    return {
        "proximos": list(deste.filter(fim__gt=agora).order_by("inicio")[:HISTORICO]),
        "anteriores": list(deste.filter(fim__lte=agora).order_by("-inicio")[:HISTORICO]),
        "total": deste.count(),
    }


@exige_permissao(Modulo.PACIENTES, Acao.CRIAR)
def novo(request):
    return _formulario(request, Patient())


@exige_permissao(Modulo.PACIENTES, Acao.ALTERAR)
def editar(request, pk):
    # An archived patient is restored before being changed.
    return _formulario(request, get_object_or_404(Patient.objects, pk=pk, arquivado=False))


def _formulario(request, patient):
    form = PacienteForm(request.POST or None, instance=patient, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        patient = form.save()
        messages.success(request, _("Paciente %(nome)s salvo.") % {"nome": patient.name})
        return redirect("patients:record", pk=patient.pk)
    return render(request, "patients/form.html", {"form": form, "patient": patient})


@exige_permissao(Modulo.PACIENTES, Acao.EXCLUIR)
def arquivar(request, pk):
    patient = get_object_or_404(Patient.objects, pk=pk, arquivado=False)
    # Not while the patient still owes or is owed money: the administrator first receives or
    # cancels those entries (0.27.2, decision 075), so finance never lists archived patients.
    abertas = list(
        Installment.objects.abertas()
        .filter(entry__patient=patient)
        .select_related("entry")
        .order_by("vencimento", "pk")
    )
    if abertas:
        if request.method == "POST":
            messages.error(
                request, _("Resolva as contas em aberto do paciente antes de arquivá-lo.")
            )
        return render(request, "patients/archive.html", {"patient": patient, "abertas": abertas})
    if request.method == "POST":
        patient.arquivado = True
        patient.arquivado_em = timezone.now()
        patient.arquivado_por = request.user
        patient.save()
        messages.success(
            request,
            _(
                "Paciente %(nome)s arquivado. O histórico continua guardado e ele pode ser "
                "restaurado na lista de pacientes, em Situação: Arquivados."
            )
            % {"nome": patient.name},
        )
        return redirect("patients:list")
    return render(request, "patients/archive.html", {"patient": patient})


@exige_permissao(Modulo.PACIENTES, Acao.EXCLUIR)
def restaurar(request, pk):
    patient = get_object_or_404(Patient.objects, pk=pk, arquivado=True)
    if request.method == "POST":
        patient.arquivado = False
        patient.arquivado_em = patient.arquivado_por = None
        patient.save()
        messages.success(request, _("Paciente %(nome)s restaurado.") % {"nome": patient.name})
    return redirect("patients:record", pk=patient.pk)


@exige_permissao(Modulo.PACIENTES, Acao.EXCLUIR)
def excluir(request, pk):
    """Permanent deletion, only for an archived patient who asked for it (LGPD, art. 18).

    The appointments stay in the schedule without the patient (and without their notes),
    the recalls, health plan cards and related people go, financial entries are kept
    (accounting history) without the patient and the notes, and the patient's personal data
    is removed from the audit log as well.
    """
    patient = get_object_or_404(Patient.objects, pk=pk, arquivado=True)
    # The country's law and how long it keeps medical records (decision 124).
    contexto = {
        "patient": patient,
        "lei": legislation.do_pais(),
        "prazo_de_guarda": legislation.prazo_de_guarda(),
    }
    # The medical record must be kept (20 years in Brazil, Law 13.787/2018, decision 081): a
    # patient with one stays archived and is never permanently deleted, in any country.
    atendimentos = Visit.objects.filter(patient=patient).count()
    if atendimentos:
        if request.method == "POST":
            messages.error(request, _("Paciente com prontuário não pode ser excluído."))
        return render(request, "patients/delete.html", {**contexto, "atendimentos": atendimentos})
    if request.method == "POST":
        code = patient.pk
        agendamentos = Appointment.objects.filter(patient=patient)
        ids_agendamentos = list(agendamentos.values_list("pk", flat=True))
        rechamadas = Recall.objects.filter(patient=patient)
        ids_rechamadas = list(rechamadas.values_list("pk", flat=True))
        carteirinhas = MemberCard.objects.filter(patient=patient)
        ids_carteirinhas = list(carteirinhas.values_list("pk", flat=True))
        # Their own relatives and contacts, and the links other patients made to them.
        relacionadas = RelatedPerson.objects.filter(Q(patient=patient) | Q(outro_paciente=patient))
        ids_relacionadas = list(relacionadas.values_list("pk", flat=True))
        lancamentos = Entry.objects.filter(patient=patient)
        ids_lancamentos = list(lancamentos.values_list("pk", flat=True))
        ids_parcelas = list(
            Installment.objects.filter(entry__in=ids_lancamentos).values_list("pk", flat=True)
        )
        ids_pagamentos = list(
            Payment.objects.filter(parcela__in=ids_parcelas).values_list("pk", flat=True)
        )
        orcamentos = Estimate.objects.filter(patient=patient)
        ids_orcamentos = list(orcamentos.values_list("pk", flat=True))
        ids_itens = list(
            EstimateItem.objects.filter(orcamento__in=ids_orcamentos).values_list("pk", flat=True)
        )
        # Stored in Portuguese, like the rest of the data. Free-text notes may hold
        # personal data, so they go too; the amounts and dates stay (accounting history).
        excluido = f"Paciente excluído (código {code})"
        with transaction.atomic():
            orcamentos.delete()  # items go with them (cascade)
            agendamentos.update(patient=None, description=excluido)
            lancamentos.update(patient=None, pessoa=excluido, notes="")
            Payment.objects.filter(pk__in=ids_pagamentos).update(note="")
            rechamadas.delete()
            carteirinhas.delete()
            relacionadas.delete()
            patient.delete()
            anonimizar(Patient, [code])
            anonimizar(Appointment, ids_agendamentos)
            anonimizar(Recall, ids_rechamadas)
            anonimizar(MemberCard, ids_carteirinhas)
            anonimizar(RelatedPerson, ids_relacionadas)
            anonimizar(Entry, ids_lancamentos)
            anonimizar(Installment, ids_parcelas)
            anonimizar(Payment, ids_pagamentos)
            anonimizar(Estimate, ids_orcamentos)
            anonimizar(EstimateItem, ids_itens)
            registrar(
                AuditEntry.Acao.EXCLUIR,
                # Filed under the clinic, so its administrator sees the erasure in the audit
                # log (review stage 4: with no object, it had no clinic and stayed hidden).
                clinic=request.clinic,
                description=f"Paciente {code}: dados pessoais excluídos a pedido do titular",
            )
        messages.success(
            request,
            _("Os dados do paciente de código %(codigo)s foram excluídos.") % {"codigo": code},
        )
        return redirect(f"{reverse('patients:list')}?situacao=arquivados")
    return render(request, "patients/delete.html", contexto)


@exige_permissao(Modulo.PACIENTES, Acao.VER)
def sugestoes(request):
    """Up to 10 active patients matching the text, for search-as-you-type fields (HTMX)."""
    busca = request.GET.get("q", "").strip()
    pacientes = filtrar(Patient.objects.all(), busca, "", "ativos")[:10] if len(busca) >= 2 else []
    return render(request, "patients/_suggestions.html", {"pacientes": pacientes})


MESES = [MONTHS[n] for n in range(1, 13)]  # translated month names (Django)


@exige_permissao(Modulo.ANIVERSARIANTES, Acao.VER)
def aniversariantes(request):
    hoje = timezone.localdate()
    mes = request.GET.get("mes", "")
    mes = int(mes) if mes.isdecimal() and 1 <= int(mes) <= 12 else hoje.month
    pacientes = Patient.objects.filter(
        active=True, arquivado=False, data_nascimento__month=mes
    ).order_by("data_nascimento__day", "name")
    ano = hoje.year if mes >= hoje.month else hoje.year + 1  # next birthday's year
    linhas = [(patient, ano - patient.data_nascimento.year) for patient in pacientes]
    return render(
        request,
        "patients/birthdays.html",
        {"mes": mes, "meses": list(enumerate(MESES, start=1)), "linhas": linhas, "hoje": hoje},
    )


# --- Related people (decision 101) ------------------------------------------------------


def relacionados_de(patient):
    """The patient's relatives and contacts, plus the patients who listed this one.

    Each item is (link, other person's name, the other patient or None, is_reverse); a
    reverse link reads "Mãe de Ana" on the mother's record.
    """
    proprios = RelatedPerson.objects.filter(patient=patient).select_related("outro_paciente")
    inversos = RelatedPerson.objects.filter(outro_paciente=patient).select_related("patient")
    return [(r, r.nome_exibido, r.outro_paciente, False) for r in proprios] + [
        (r, r.patient.name, r.patient, True) for r in inversos
    ]


@exige_permissao(Modulo.PACIENTES, Acao.ALTERAR)
def relacionado_novo(request, pk):
    patient = get_object_or_404(Patient.objects, pk=pk, arquivado=False)
    return _relacionado(request, patient, RelatedPerson())


@exige_permissao(Modulo.PACIENTES, Acao.ALTERAR)
def relacionado_editar(request, pk):
    relacionada = get_object_or_404(
        RelatedPerson.objects.select_related("patient", "outro_paciente"),
        pk=pk,
        patient__arquivado=False,
    )
    return _relacionado(request, relacionada.patient, relacionada)


def _relacionado(request, patient, instancia):
    form = PessoaRelacionadaForm(request.POST or None, instance=instancia, patient=patient)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Pessoa relacionada salva."))
        return redirect("patients:record", pk=patient.pk)
    # The patient chosen in the search box, shown again when the form comes back.
    if form.is_bound:
        outro = form.cleaned_data.get("outro_paciente")
    else:
        outro = instancia.outro_paciente if instancia.outro_paciente_id else None
    return render(
        request,
        "patients/related_form.html",
        {
            "form": form,
            "patient": patient,
            "instancia": instancia,
            "outro": outro,
        },
    )


@exige_permissao(Modulo.PACIENTES, Acao.ALTERAR)
def relacionado_remover(request, pk):
    relacionada = get_object_or_404(RelatedPerson.objects, pk=pk, patient__arquivado=False)
    if request.method == "POST":
        patient = relacionada.patient_id
        relacionada.delete()
        messages.success(request, _("Pessoa relacionada removida."))
        return redirect("patients:record", pk=patient)
    return redirect("patients:related_edit", pk=pk)
