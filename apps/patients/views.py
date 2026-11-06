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
from apps.audit.record import anonymize, log_event
from apps.core import legislation
from apps.core.permissions import Action, Module, can, requires_permission
from apps.core.validators import normalize_cnpj
from apps.estimates.models import Estimate, EstimateItem
from apps.finance.models import Entry, Installment, Payment
from apps.finance.services import patient_summary
from apps.health_plans.models import MemberCard
from apps.medical_records.models import Visit
from apps.medical_records.permissions import accesses_medical_records
from apps.recalls.models import Recall
from apps.schedule.models import Appointment
from apps.schedule.services import visible_appointments

from .forms import PatientForm, RelatedPersonForm
from .models import Patient, RelatedPerson

PER_PAGE = 50
STATUSES = {
    "ativos": Q(active=True, archived=False),
    "inativos": Q(active=False, archived=False),
    "todos": Q(archived=False),
    "arquivados": Q(archived=True),  # clinic administrators only (see lista)
}


def _sees_archived(request):
    """Archived patients are seen (and restored or deleted) only by who could delete."""
    return can(request, Module.PATIENTS, Action.DELETE)


def _visible_patients(request):
    if _sees_archived(request):
        return Patient.objects.all()
    return Patient.objects.filter(archived=False)


def filter_patients(patients, search, kind, status):
    """Search by name/company name (accent-insensitive), CPF/CNPJ prefix or patient code."""
    if search:
        query_filter = Q(name__unaccent__icontains=search) | Q(
            legal_name__unaccent__icontains=search
        )
        document = normalize_cnpj(search)
        if len(document) >= 3 and not any(c.isspace() for c in search.strip()):
            query_filter |= Q(tax_id__startswith=document)
        if search.isdecimal() and len(search) <= 9:
            query_filter |= Q(pk=int(search))
        patients = patients.filter(query_filter)
    if kind in Patient.Kind.values:
        patients = patients.filter(kind=kind)
    return patients.filter(STATUSES.get(status, STATUSES["ativos"]))


@requires_permission(Module.PATIENTS, Action.VIEW)
def patient_list(request):
    search = request.GET.get("q", "").strip()
    kind = request.GET.get("kind", "")
    status = request.GET.get("status", "ativos")
    if status == "arquivados" and not _sees_archived(request):
        status = "ativos"
    patients = filter_patients(Patient.objects.select_related("city__state"), search, kind, status)
    page = Paginator(patients, PER_PAGE).get_page(request.GET.get("page"))
    return render(
        request,
        "patients/list.html",
        {
            "page": page,
            "search": search,
            "kind": kind,
            "status": status,
            "types": Patient.Kind.choices,
            "query": urlencode({"q": search, "kind": kind, "status": status}),
        },
    )


@requires_permission(Module.PATIENTS, Action.VIEW)
def patient_record(request, pk):
    patient = get_object_or_404(
        _visible_patients(request).select_related("city__state", "marital_status", "archived_by"),
        pk=pk,
    )
    # LGPD: access to a patient's record (health data) is logged.
    log_event(AuditEntry.Action.VIEWED, patient)
    recalls = Recall.objects.filter(patient=patient).order_by("-date")[:20]
    context = {"patient": patient, "recalls": recalls}
    if can(request, Module.SCHEDULE, Action.VIEW):
        context["appointments"] = _history(request, patient)
    if can(request, Module.RECEIVING, Action.VIEW):
        context["finance"] = patient_summary(patient)
    if can(request, Module.ESTIMATES, Action.VIEW):
        context["estimates"] = list(
            Estimate.objects.filter(patient=patient).prefetch_related("items")[:10]
        )
    if can(request, Module.HEALTH_PLANS, Action.VIEW):
        context["plan_cards"] = list(
            MemberCard.objects.filter(patient=patient).select_related("health_plan")
        )
    context["related_people"] = related_of(patient)
    if accesses_medical_records(request):
        context["medical_record"] = list(
            Visit.objects.filter(patient=patient).select_related("practitioner")
        )
    return render(request, "patients/record.html", context)


@requires_permission(Module.PATIENTS, Action.VIEW)
def print_patient(request, pk):
    """The registration sheet, ready to print or save as PDF (as the legacy Medical's
    fichapaciente_imp): identification, contact, address and health plan cards."""
    patient = get_object_or_404(
        _visible_patients(request).select_related("city__state", "marital_status"), pk=pk
    )
    log_event(AuditEntry.Action.VIEWED, patient)  # LGPD, as the record
    member_cards = (
        list(MemberCard.objects.filter(patient=patient, active=True).select_related("health_plan"))
        if can(request, Module.HEALTH_PLANS, Action.VIEW)
        else None
    )
    return render(
        request,
        "patients/print.html",
        {
            "patient": patient,
            "plan_cards": member_cards,
            "related_people": RelatedPerson.objects.filter(patient=patient).select_related(
                "other_patient"
            ),
            "today": timezone.localdate(),
        },
    )


HISTORY = 10  # appointments shown in each list of the patient record


def _history(request, patient):
    """The patient's next and latest appointments (practitioners: only their own)."""
    of_patient = (
        visible_appointments(request).filter(patient=patient).select_related("practitioner", "kind")
    )
    now = timezone.now()
    return {
        "upcoming": list(of_patient.filter(end__gt=now).order_by("start")[:HISTORY]),
        "past": list(of_patient.filter(end__lte=now).order_by("-start")[:HISTORY]),
        "total": of_patient.count(),
    }


@requires_permission(Module.PATIENTS, Action.CREATE)
def new_patient(request):
    return _patient_form(request, Patient())


@requires_permission(Module.PATIENTS, Action.CHANGE)
def edit_patient(request, pk):
    # An archived patient is restored before being changed.
    return _patient_form(request, get_object_or_404(Patient.objects, pk=pk, archived=False))


def _patient_form(request, patient):
    form = PatientForm(request.POST or None, instance=patient, clinic=request.clinic)
    if request.method == "POST" and form.is_valid():
        patient = form.save()
        messages.success(request, _("Paciente %(nome)s salvo.") % {"nome": patient.name})
        return redirect("patients:record", pk=patient.pk)
    return render(request, "patients/form.html", {"form": form, "patient": patient})


@requires_permission(Module.PATIENTS, Action.DELETE)
def archive(request, pk):
    patient = get_object_or_404(Patient.objects, pk=pk, archived=False)
    # Not while the patient still owes or is owed money: the administrator first receives or
    # cancels those entries (0.27.2, decision 075), so finance never lists archived patients.
    unpaid = list(
        Installment.objects.unpaid()
        .filter(entry__patient=patient)
        .select_related("entry")
        .order_by("due_date", "pk")
    )
    if unpaid:
        if request.method == "POST":
            messages.error(
                request, _("Resolva as contas em aberto do paciente antes de arquivá-lo.")
            )
        return render(request, "patients/archive.html", {"patient": patient, "open_items": unpaid})
    if request.method == "POST":
        patient.archived = True
        patient.archived_at = timezone.now()
        patient.archived_by = request.user
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


@requires_permission(Module.PATIENTS, Action.DELETE)
def restore(request, pk):
    patient = get_object_or_404(Patient.objects, pk=pk, archived=True)
    if request.method == "POST":
        patient.archived = False
        patient.archived_at = patient.archived_by = None
        patient.save()
        messages.success(request, _("Paciente %(nome)s restaurado.") % {"nome": patient.name})
    return redirect("patients:record", pk=patient.pk)


@requires_permission(Module.PATIENTS, Action.DELETE)
def delete_patient(request, pk):
    """Permanent deletion, only for an archived patient who asked for it (LGPD, art. 18).

    The appointments stay in the schedule without the patient (and without their notes),
    the recalls, health plan cards and related people go, financial entries are kept
    (accounting history) without the patient and the notes, and the patient's personal data
    is removed from the audit log as well.
    """
    patient = get_object_or_404(Patient.objects, pk=pk, archived=True)
    # The country's law and how long it keeps medical records (decision 124).
    context = {
        "patient": patient,
        "law": legislation.for_country(),
        "retention_period": legislation.retention_period(),
    }
    # The medical record must be kept (20 years in Brazil, Law 13.787/2018, decision 081): a
    # patient with one stays archived and is never permanently deleted, in any country.
    visits = Visit.objects.filter(patient=patient).count()
    if visits:
        if request.method == "POST":
            messages.error(request, _("Paciente com prontuário não pode ser excluído."))
        return render(request, "patients/delete.html", {**context, "visits": visits})
    if request.method == "POST":
        code = patient.pk
        appointments = Appointment.objects.filter(patient=patient)
        appointment_ids = list(appointments.values_list("pk", flat=True))
        recalls = Recall.objects.filter(patient=patient)
        recall_ids = list(recalls.values_list("pk", flat=True))
        member_cards = MemberCard.objects.filter(patient=patient)
        member_card_ids = list(member_cards.values_list("pk", flat=True))
        # Their own relatives and contacts, and the links other patients made to them.
        related_people = RelatedPerson.objects.filter(Q(patient=patient) | Q(other_patient=patient))
        related_person_ids = list(related_people.values_list("pk", flat=True))
        entries = Entry.objects.filter(patient=patient)
        entry_ids = list(entries.values_list("pk", flat=True))
        installment_ids = list(
            Installment.objects.filter(entry__in=entry_ids).values_list("pk", flat=True)
        )
        payment_ids = list(
            Payment.objects.filter(installment__in=installment_ids).values_list("pk", flat=True)
        )
        estimates = Estimate.objects.filter(patient=patient)
        estimate_ids = list(estimates.values_list("pk", flat=True))
        item_ids = list(
            EstimateItem.objects.filter(estimate__in=estimate_ids).values_list("pk", flat=True)
        )
        # Stored in Portuguese, like the rest of the data. Free-text notes may hold
        # personal data, so they go too; the amounts and dates stay (accounting history).
        deleted_one = f"Paciente excluído (código {code})"
        with transaction.atomic():
            estimates.delete()  # items go with them (cascade)
            appointments.update(patient=None, description=deleted_one)
            entries.update(patient=None, payer=deleted_one, notes="")
            Payment.objects.filter(pk__in=payment_ids).update(note="")
            recalls.delete()
            member_cards.delete()
            related_people.delete()
            patient.delete()
            anonymize(Patient, [code])
            anonymize(Appointment, appointment_ids)
            anonymize(Recall, recall_ids)
            anonymize(MemberCard, member_card_ids)
            anonymize(RelatedPerson, related_person_ids)
            anonymize(Entry, entry_ids)
            anonymize(Installment, installment_ids)
            anonymize(Payment, payment_ids)
            anonymize(Estimate, estimate_ids)
            anonymize(EstimateItem, item_ids)
            log_event(
                AuditEntry.Action.DELETE,
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
    return render(request, "patients/delete.html", context)


@requires_permission(Module.PATIENTS, Action.VIEW)
def suggestions(request):
    """Up to 10 active patients matching the text, for search-as-you-type fields (HTMX)."""
    search = request.GET.get("q", "").strip()
    patients = (
        filter_patients(Patient.objects.all(), search, "", "ativos")[:10]
        if len(search) >= 2
        else []
    )
    return render(request, "patients/_suggestions.html", {"patients": patients})


MONTH_NAMES = [MONTHS[n] for n in range(1, 13)]  # translated month names (Django)


@requires_permission(Module.BIRTHDAYS, Action.VIEW)
def birthdays(request):
    today = timezone.localdate()
    month = request.GET.get("month", "")
    month = int(month) if month.isdecimal() and 1 <= int(month) <= 12 else today.month
    patients = Patient.objects.filter(
        active=True, archived=False, birth_date__month=month
    ).order_by("birth_date__day", "name")
    year = today.year if month >= today.month else today.year + 1  # next birthday's year
    rows = [(patient, year - patient.birth_date.year) for patient in patients]
    return render(
        request,
        "patients/birthdays.html",
        {
            "month": month,
            "months": list(enumerate(MONTH_NAMES, start=1)),
            "rows": rows,
            "today": today,
        },
    )


# --- Related people (decision 101) ------------------------------------------------------


def related_of(patient):
    """The patient's relatives and contacts, plus the patients who listed this one.

    Each item is (link, other person's name, the other patient or None, is_reverse); a
    reverse link reads "Mãe de Ana" on the mother's record.
    """
    own_ones = RelatedPerson.objects.filter(patient=patient).select_related("other_patient")
    inverse = RelatedPerson.objects.filter(other_patient=patient).select_related("patient")
    return [(r, r.display_name, r.other_patient, False) for r in own_ones] + [
        (r, r.patient.name, r.patient, True) for r in inverse
    ]


@requires_permission(Module.PATIENTS, Action.CHANGE)
def new_related_person(request, pk):
    patient = get_object_or_404(Patient.objects, pk=pk, archived=False)
    return _related_person_form(request, patient, RelatedPerson())


@requires_permission(Module.PATIENTS, Action.CHANGE)
def edit_related_person(request, pk):
    related_person = get_object_or_404(
        RelatedPerson.objects.select_related("patient", "other_patient"),
        pk=pk,
        patient__archived=False,
    )
    return _related_person_form(request, related_person.patient, related_person)


def _related_person_form(request, patient, instance):
    form = RelatedPersonForm(request.POST or None, instance=instance, patient=patient)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Pessoa relacionada salva."))
        return redirect("patients:record", pk=patient.pk)
    # The patient chosen in the search box, shown again when the form comes back.
    if form.is_bound:
        other = form.cleaned_data.get("other_patient")
    else:
        other = instance.other_patient if instance.other_patient_id else None
    return render(
        request,
        "patients/related_form.html",
        {
            "form": form,
            "patient": patient,
            "instance": instance,
            "other": other,
        },
    )


@requires_permission(Module.PATIENTS, Action.CHANGE)
def remove_related_person(request, pk):
    related_person = get_object_or_404(RelatedPerson.objects, pk=pk, patient__archived=False)
    if request.method == "POST":
        patient = related_person.patient_id
        related_person.delete()
        messages.success(request, _("Pessoa relacionada removida."))
        return redirect("patients:record", pk=patient)
    return redirect("patients:related_edit", pk=pk)
