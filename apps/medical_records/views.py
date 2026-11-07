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
from apps.audit.record import log_event
from apps.core import modules
from apps.core.models import ModuleCode
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.schedule.models import Appointment

from .forms import (
    AddendumForm,
    AttachmentForm,
    CertificateForm,
    ExamRequestForm,
    PrescriptionForm,
    VisitForm,
)
from .models import ANAMNESIS_FIELDS, Attachment, Certificate, ExamRequest, Prescription, Visit
from .permissions import accesses_medical_records, manages_medical_records, user_practitioner

Action = AuditEntry.Action
# The audit log names the changed fields but never copies clinical text (decision 081).
CONFIDENTIAL = "(conteúdo clínico)"


def requires_practitioner(view):
    """Only practitioners and the system administrator reach the medical record; the view
    gets the user's Profissional (None for a system administrator who is not one)."""

    @wraps(view)
    @login_required
    def protected(request, *args, **kwargs):
        if not accesses_medical_records(request):
            raise PermissionDenied
        modules.mark_if_disabled(request, ModuleCode.MEDICAL_RECORDS)
        return view(request, user_practitioner(request), *args, **kwargs)

    return protected


def _audit(action, visit, fields):
    if fields:
        log_event(action, visit, changes={field: [CONFIDENTIAL, CONFIDENTIAL] for field in fields})


def _finalize(request, visit):
    visit.finalized_at = timezone.now()
    visit.finalized_by = request.user
    visit.save(update_fields=["finalized_at", "finalized_by", "updated_at"])
    log_event(Action.CHANGE, visit, changes={"finalized": [None, "yes"]})
    messages.success(request, _("Visit finalized. From now on, corrections are made by addendum."))


@requires_practitioner
def new_visit(request, practitioner, patient):
    patient = get_object_or_404(Patient.objects, pk=patient, archived=False)
    appointment = None
    code = request.POST.get("appointment") or request.GET.get("appointment") or ""
    if code.isdecimal():
        appointment = get_object_or_404(Appointment.objects, pk=code, patient=patient)
        existing_one = Visit.objects.filter(appointment=appointment).first()
        if existing_one is not None:
            return redirect("medical_records:visit", pk=existing_one.pk)
    initial = {"date": appointment.start if appointment else timezone.now()}
    practitioners = None
    if manages_medical_records(request):
        practitioners = Practitioner.objects.filter(active=True)
        initial["practitioner"] = appointment.practitioner if appointment else practitioner
    form = VisitForm(request.POST or None, initial=initial, practitioners=practitioners)
    if request.method == "POST" and form.is_valid():
        visit = form.save(commit=False)
        visit.patient = patient
        visit.practitioner = form.cleaned_data.get("practitioner") or practitioner
        visit.appointment = appointment
        visit.created_by = request.user
        visit.save()
        _audit(Action.CREATE, visit, [c for c in ANAMNESIS_FIELDS if getattr(visit, c)])
        if request.POST.get("action") == "finalize":
            _finalize(request, visit)
        else:
            messages.success(request, _("Visit saved."))
        return redirect("medical_records:visit", pk=visit.pk)
    return render(
        request,
        "medical_records/visit.html",
        {"form": form, "patient": patient, "appointment": appointment, "editable": True},
    )


@requires_practitioner
def visit(request, practitioner, pk):
    visit = get_object_or_404(
        Visit.objects.select_related("patient", "practitioner", "appointment"), pk=pk
    )
    # Only its author (or the system administrator) changes a visit, until it is finalized.
    manages = manages_medical_records(request)
    by_author = practitioner is not None and visit.practitioner_id == practitioner.pk
    editavel = not visit.is_finalized and (by_author or manages)
    form = VisitForm(request.POST or None, instance=visit) if editavel else None
    if request.method == "POST":
        if not editavel:
            raise PermissionDenied
        if form.is_valid():
            changed_ones = list(form.changed_data)
            form.save()
            _audit(Action.CHANGE, visit, changed_ones)
            if request.POST.get("action") == "finalize":
                _finalize(request, visit)
            else:
                messages.success(request, _("Visit saved."))
            return redirect("medical_records:visit", pk=visit.pk)
    else:
        log_event(Action.VIEWED, visit)
    return render(
        request,
        "medical_records/visit.html",
        {
            "visit": visit,
            "patient": visit.patient,
            "appointment": visit.appointment,
            "form": form,
            "editable": editavel,
            "fields": _fields(visit),
            "addenda": visit.addenda.select_related("practitioner"),
            "addendum_form": AddendumForm() if visit.is_finalized else None,
            # Certificates and prescriptions are issued by the visit's author (decision 082).
            "issues_documents": by_author or manages,
            "is_admin": manages,
            "certificates": visit.certificates.all(),
            "prescriptions": visit.prescriptions.all(),
            "exam_requests": visit.exam_requests.all(),
            # Never the file contents in a list.
            "attachments": visit.attachments.defer("content").select_related("practitioner"),
            "attachment_form": AttachmentForm(),
            "can_remove_attachments": not visit.is_finalized,
        },
    )


def _fields(visit):
    return [
        (visit._meta.get_field(field).verbose_name, getattr(visit, field))
        for field in ANAMNESIS_FIELDS
    ]


def _by_author(request, practitioner, pk):
    """The visit, if the user is its author or the system administrator."""
    visit = get_object_or_404(Visit.objects.select_related("patient"), pk=pk)
    by_author = practitioner is not None and visit.practitioner_id == practitioner.pk
    if not (by_author or manages_medical_records(request)):
        raise PermissionDenied
    return visit


@requires_practitioner
def print_visit(request, practitioner, pk):
    """The finalized visit, ready to print and sign (without a digital signature, the
    printed and signed copy is the legal record)."""
    visit = get_object_or_404(Visit.objects.select_related("patient", "practitioner"), pk=pk)
    if not visit.is_finalized:
        raise PermissionDenied
    log_event(Action.VIEWED, visit, description=f"{visit} (impressão)")
    return render(
        request,
        "medical_records/print.html",
        {
            "visit": visit,
            "fields": _fields(visit),
            "addenda": visit.addenda.select_related("practitioner"),
        },
    )


@requires_practitioner
def new_certificate(request, practitioner, pk):
    visit = _by_author(request, practitioner, pk)
    appointment = visit.appointment
    timestamp = timezone.localtime(appointment.start if appointment else visit.date)
    initial = {
        "date": timestamp.date(),
        "start_time": timestamp.time().replace(second=0, microsecond=0),
        "end_time": timezone.localtime(appointment.end).time() if appointment else None,
    }
    form = CertificateForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        certificate = form.save(commit=False)
        certificate.visit = visit
        certificate.practitioner = visit.practitioner
        certificate.created_by = request.user
        certificate.save()
        log_event(
            Action.CREATE,
            certificate,
            changes={
                "kind": [None, certificate.kind],
                "days": [None, certificate.days],
                **({"note": [None, CONFIDENTIAL]} if certificate.note else {}),
            },
        )
        messages.success(request, _("Certificate issued."))
        return redirect("medical_records:certificate", pk=certificate.pk)
    return render(
        request,
        "medical_records/document_form.html",
        {"form": form, "visit": visit, "title": _("Issue certificate")},
    )


@requires_practitioner
def new_prescription(request, practitioner, pk):
    visit = _by_author(request, practitioner, pk)
    form = PrescriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        prescription = form.save(commit=False)
        prescription.visit = visit
        prescription.practitioner = visit.practitioner
        prescription.created_by = request.user
        prescription.save()
        log_event(Action.CREATE, prescription, changes={"medications": [None, CONFIDENTIAL]})
        messages.success(request, _("Prescription issued."))
        return redirect("medical_records:prescription", pk=prescription.pk)
    return render(
        request,
        "medical_records/document_form.html",
        {"form": form, "visit": visit, "title": _("Issue prescription")},
    )


@requires_practitioner
def certificate(request, practitioner, pk):
    certificate = get_object_or_404(
        Certificate.objects.select_related("visit__patient", "practitioner"), pk=pk
    )
    log_event(Action.VIEWED, certificate)
    return render(request, "medical_records/certificate.html", {"certificate": certificate})


@requires_practitioner
def prescription(request, practitioner, pk):
    prescription = get_object_or_404(
        Prescription.objects.select_related("visit__patient", "practitioner"), pk=pk
    )
    log_event(Action.VIEWED, prescription)
    rows = [row for row in prescription.medications.splitlines() if row.strip()]
    return render(
        request, "medical_records/prescription.html", {"prescription": prescription, "rows": rows}
    )


@require_POST
@requires_practitioner
def addendum(request, practitioner, pk):
    visit = get_object_or_404(Visit.objects, pk=pk)
    if not visit.is_finalized:
        raise PermissionDenied  # before finalizing, the author simply edits the visit
    form = AddendumForm(request.POST)
    if form.is_valid():
        addendum = form.save(commit=False)
        addendum.visit = visit
        addendum.practitioner = practitioner or visit.practitioner
        addendum.created_by = request.user
        addendum.save()
        log_event(Action.CREATE, addendum, changes={"text": [None, CONFIDENTIAL]})
        messages.success(request, _("Addendum added."))
    else:
        messages.error(request, _("Write the addendum."))
    return redirect("medical_records:visit", pk=visit.pk)


@requires_practitioner
def new_exam_request(request, practitioner, pk):
    visit = _by_author(request, practitioner, pk)
    form = ExamRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        exam_order = form.save(commit=False)
        exam_order.visit = visit
        exam_order.practitioner = visit.practitioner
        exam_order.created_by = request.user
        exam_order.save()
        log_event(
            Action.CREATE,
            exam_order,
            changes={
                "exams": [None, CONFIDENTIAL],
                **({"indication": [None, CONFIDENTIAL]} if exam_order.indication else {}),
            },
        )
        messages.success(request, _("Exam request issued."))
        return redirect("medical_records:exam_request", pk=exam_order.pk)
    return render(
        request,
        "medical_records/document_form.html",
        {"form": form, "visit": visit, "title": _("Request exams")},
    )


@requires_practitioner
def exam_request(request, practitioner, pk):
    exam_order = get_object_or_404(
        ExamRequest.objects.select_related("visit__patient", "practitioner"), pk=pk
    )
    log_event(Action.VIEWED, exam_order)
    rows = [row for row in exam_order.exams.splitlines() if row.strip()]
    return render(
        request, "medical_records/exam_request.html", {"exam_request": exam_order, "rows": rows}
    )


@require_POST
@requires_practitioner
def upload_attachment(request, practitioner, pk):
    """Any practitioner adds files to a visit, even a finalized one (results arrive later)."""
    visit = get_object_or_404(Visit.objects, pk=pk)
    if request.user.demo:
        messages.error(request, _("Demo accounts cannot upload attachments."))
        return redirect("medical_records:visit", pk=visit.pk)
    form = AttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        file = form.cleaned_data["file"]
        attachment = Attachment.objects.create(
            visit=visit,
            description=form.cleaned_data["description"],
            name=file.name[:255],
            kind=file.checked_kind,
            size=file.size,
            content=file.read(),
            practitioner=practitioner or visit.practitioner,
            created_by=request.user,
        )
        log_event(
            Action.CREATE,
            attachment,
            description=f"{visit} – {_('attachment')}",
            changes={"file": [None, CONFIDENTIAL]},
        )
        messages.success(request, _("Attachment added."))
    else:
        messages.error(request, " ".join(e for errors in form.errors.values() for e in errors))
    return redirect("medical_records:visit", pk=visit.pk)


@requires_practitioner
def attachment(request, practitioner, pk):
    attachment = get_object_or_404(Attachment.objects.select_related("visit"), pk=pk)
    log_event(Action.VIEWED, attachment, description=f"{attachment.visit} – {_('attachment')}")
    response = HttpResponse(bytes(attachment.content), content_type=attachment.kind)
    # Opened in the browser (only PDF, JPG and PNG are ever stored), never cached.
    name = "".join(c for c in attachment.name if c.isalnum() or c in "._- ") or "anexo"
    response["Content-Disposition"] = f'inline; filename="{name}"'
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
@requires_practitioner
def remove_attachment(request, practitioner, pk):
    """Who sent a file (or the system administrator) removes it while the visit is still a
    draft; afterwards it stays."""
    attachment = get_object_or_404(
        Attachment.objects.select_related("visit").defer("content"), pk=pk
    )
    sender = attachment.created_by_id == request.user.pk
    if attachment.visit.is_finalized or not (sender or manages_medical_records(request)):
        raise PermissionDenied
    visit = attachment.visit
    log_event(
        Action.DELETE,
        attachment,
        description=f"{visit} – {_('attachment')}",
        changes={"file": [CONFIDENTIAL, None]},
    )
    attachment.delete()
    messages.success(request, _("Attachment removed."))
    return redirect("medical_records:visit", pk=visit.pk)
