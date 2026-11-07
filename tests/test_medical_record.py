"""Medical record (0.29.0, decision 081): anamnesis per visit, for practitioners only."""

import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.medical_records.models import Visit
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.schedule import services as agenda
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db

ANAMNESIS = {
    "date": "2031-03-05T10:00",
    "chief_complaint": "Dor de cabeça há 3 dias",
    "present_illness": "Piora à tarde",
    "medical_history": "Alergia a dipirona",
    "physical_exam": "PA 12x8",
    "plan": "Retorno em 7 dias",
}


def user_client(user):
    """A client of its own for each user (the shared fixture logs one user at a time)."""
    new_visit = Client()
    new_visit.force_login(user)
    return new_visit


@pytest.fixture
def scenario(clinic_a, create_user, create_practitioner):
    users = {
        "dra": create_user("dra", clinic_a, Role.PRACTITIONER),
        "dr": create_user("dr", clinic_a, Role.PRACTITIONER),
        "reception": create_user("recepcao", clinic_a, Role.FRONT_DESK),
        "admin": create_user("admin", clinic_a, Role.ADMIN),
    }
    ana = create_practitioner(clinic_a, "Dra. Ana")
    bruno = create_practitioner(clinic_a, "Dr. Bruno")
    with use_clinic(clinic_a):
        Practitioner.objects.filter(pk=ana.pk).update(user=users["dra"])
        Practitioner.objects.filter(pk=bruno.pk).update(user=users["dr"])
        patient = Patient.objects.create(name="Maria Paciente")
        appointment = Appointment.objects.create(
            practitioner=ana,
            kind=AppointmentType.objects.first(),
            patient=patient,
            start=agenda.timestamp(datetime.date(2031, 3, 5), datetime.time(10)),
            end=agenda.timestamp(datetime.date(2031, 3, 5), datetime.time(11)),
        )
    return {
        "clinic": clinic_a,
        "patient": patient,
        "appointment": appointment,
        "ana": ana,
        **{name: user_client(user) for name, user in users.items()},
    }


def log_event(scenario, who="dra", **extra):
    url = reverse("medical_records:new", args=[scenario["patient"].pk])
    response = scenario[who].post(url, {**ANAMNESIS, **extra})
    assert response.status_code == 302, response.content.decode()[:500]
    with use_clinic(scenario["clinic"]):
        return Visit.objects.latest("pk")


def test_only_practitioners_see_the_record(scenario, django_user_model):
    new_visit = reverse("medical_records:new", args=[scenario["patient"].pk])
    patient_record = reverse("patients:record", args=[scenario["patient"].pk])
    for who in ("reception", "admin"):
        assert scenario[who].get(new_visit).status_code == 403
        assert "prontuario" not in scenario[who].get(patient_record).context
    # The system administrator always reaches it (decision 087), the clinic administrator not.
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    assert user_client(root).get(new_visit).status_code == 200
    page = scenario["dra"].get(patient_record)
    assert page.context["medical_record"] == [] and "Novo atendimento" in page.content.decode()

    # An administrator who is also a registered practitioner reaches it.
    with use_clinic(scenario["clinic"]):
        Practitioner.objects.create(
            name="Dr. Admin", user=django_user_model.objects.get(username="admin")
        )
    assert scenario["admin"].get(new_visit).status_code == 200


def test_register_save_and_finalize(scenario):
    appointment = scenario["appointment"]
    visit = log_event(scenario, appointment=appointment.pk)
    assert (visit.practitioner, visit.appointment) == (scenario["ana"], appointment)
    assert visit.chief_complaint == ANAMNESIS["chief_complaint"]
    assert not visit.is_finalized
    # The appointment leads to the same visit, never a second one.
    new_url = reverse("medical_records:new", args=[scenario["patient"].pk])
    response = scenario["dra"].get(new_url, {"appointment": appointment.pk})
    assert response.url == reverse("medical_records:visit", args=[visit.pk])

    url = reverse("medical_records:visit", args=[visit.pk])
    scenario["dra"].post(url, {**ANAMNESIS, "plan": "Retorno em 15 dias", "action": "finalize"})
    visit.refresh_from_db()
    assert visit.is_finalized and visit.plan == "Retorno em 15 dias"

    # Finalized: nobody changes it any more, corrections are addenda.
    assert scenario["dra"].post(url, {**ANAMNESIS, "plan": "outra"}).status_code == 403
    page = scenario["dra"].get(url)
    assert page.context["form"] is None and page.context["addendum_form"] is not None
    scenario["dr"].post(reverse("medical_records:addendum", args=[visit.pk]), {"text": "Exame ok"})
    with use_clinic(scenario["clinic"]):
        addendum = visit.addenda.get()
    assert addendum.text == "Exame ok" and addendum.practitioner.name == "Dr. Bruno"
    assert "Exame ok" in scenario["dra"].get(url).content.decode()


def test_only_author_changes_draft(scenario):
    visit = log_event(scenario)
    url = reverse("medical_records:visit", args=[visit.pk])
    page = scenario["dr"].get(url)
    assert page.context["form"] is None and page.context["addendum_form"] is None
    assert scenario["dr"].post(url, {**ANAMNESIS, "plan": "outra"}).status_code == 403
    # No addendum before it is finalized: the author edits the draft instead.
    addendum = reverse("medical_records:addendum", args=[visit.pk])
    assert scenario["dra"].post(addendum, {"text": "x"}).status_code == 403


def test_audit_logs_without_copying_clinical_text(scenario):
    visit = log_event(scenario)
    scenario["dr"].get(reverse("medical_records:visit", args=[visit.pk]))
    records = AuditEntry.objects.filter(model_name="Atendimento", object_id=visit.pk)
    assert {r.action for r in records} == {"create", "viewed"}
    content = str([r.changes for r in records])
    assert "(conteúdo clínico)" in content
    for text in ANAMNESIS.values():
        if not text.startswith("2031"):
            assert text not in content


def test_patient_with_record_is_not_deleted(scenario, django_user_model):
    log_event(scenario)
    patient = scenario["patient"]
    with use_clinic(scenario["clinic"]):
        Patient.objects.filter(pk=patient.pk).update(archived=True, archived_at=timezone.now())
    url = reverse("patients:delete", args=[patient.pk])
    page = scenario["admin"].get(url)
    assert page.context["visits"] == 1 and "20 anos" in page.content.decode()
    scenario["admin"].post(url)
    with use_clinic(scenario["clinic"]):
        assert Patient.objects.filter(pk=patient.pk).exists()


def test_schedule_leads_to_visit_only_for_practitioners(scenario):
    edit = reverse("schedule:edit", args=[scenario["appointment"].pk])
    assert "Registrar atendimento" in scenario["dra"].get(edit).content.decode()
    assert "Registrar atendimento" not in scenario["reception"].get(edit).content.decode()
    visit = log_event(scenario, appointment=scenario["appointment"].pk)
    page = scenario["dra"].get(edit).content.decode()
    assert reverse("medical_records:visit", args=[visit.pk]) in page


def test_print_only_after_finalized(scenario):
    visit = log_event(scenario)
    url = reverse("medical_records:print", args=[visit.pk])
    assert scenario["dra"].get(url).status_code == 403
    page = scenario["dra"].get(reverse("medical_records:visit", args=[visit.pk]))
    assert url not in page.content.decode()
    scenario["dra"].post(
        reverse("medical_records:visit", args=[visit.pk]),
        {**ANAMNESIS, "action": "finalize"},
    )
    printout = scenario["dr"].get(url)
    content = printout.content.decode()
    assert printout.status_code == 200
    assert ANAMNESIS["chief_complaint"] in content and "Dra. Ana" in content
    assert AuditEntry.objects.filter(
        object_id=visit.pk, action="viewed", object_repr__endswith="(impressão)"
    ).exists()
    assert scenario["reception"].get(url).status_code == 403


def test_attendance_and_leave_certificates(scenario):
    visit = log_event(scenario, appointment=scenario["appointment"].pk)
    url = reverse("medical_records:certificate_new", args=[visit.pk])
    # The appointment's times come filled in.
    form_page = scenario["dra"].get(url).context["form"]
    assert form_page.initial["start_time"] == datetime.time(10)
    assert form_page.initial["end_time"] == datetime.time(11)

    response = scenario["dra"].post(
        url,
        {
            "kind": "attendance",
            "date": "2031-03-05",
            "start_time": "10:00",
            "end_time": "11:00",
        },
    )
    page = scenario["dra"].get(response.url).content.decode()
    assert "Maria Paciente" in page and "das 10:00 às 11:00" in page

    without_days = scenario["dra"].post(url, {"kind": "sick_leave", "date": "2031-03-05"})
    assert "Informe quantos dias" in without_days.content.decode()
    response = scenario["dra"].post(
        url, {"kind": "sick_leave", "date": "2031-03-05", "days": "3", "note": "Repouso"}
    )
    page = scenario["dra"].get(response.url).content.decode()
    assert "3 dias de afastamento" in page and "Repouso" in page
    assert "5 de março de 2031" in page  # month in lower case, as in running text
    with use_clinic(scenario["clinic"]):
        assert visit.certificates.count() == 2
    record = AuditEntry.objects.filter(model_name="Atestado").latest("pk")
    assert "Repouso" not in str(record.changes)

    # Only the visit's author issues documents; other practitioners print them.
    assert scenario["dr"].get(url).status_code == 403
    assert scenario["dr"].get(response.url).status_code == 200
    assert scenario["reception"].get(response.url).status_code == 403


def test_prescription_one_line_per_item(scenario):
    visit = log_event(scenario)
    url = reverse("medical_records:prescription_new", args=[visit.pk])
    medications = "Paracetamol 750 mg, 1 comprimido de 6 em 6 horas\n\nSoro fisiológico nasal"
    response = scenario["dra"].post(url, {"medications": medications})
    page = scenario["dra"].get(response.url)
    assert page.context["rows"] == [
        "Paracetamol 750 mg, 1 comprimido de 6 em 6 horas",
        "Soro fisiológico nasal",
    ]
    assert "RECEITUÁRIO" in page.content.decode()
    patient_record = scenario["dra"].get(reverse("medical_records:visit", args=[visit.pk]))
    assert response.url in patient_record.content.decode()
    record = AuditEntry.objects.filter(model_name="Receita").latest("pk")
    assert "Paracetamol" not in str(record.changes)


def test_exam_request(scenario):
    visit = log_event(scenario)
    url = reverse("medical_records:exam_request_new", args=[visit.pk])
    response = scenario["dra"].post(
        url, {"exams": "Hemograma completo\nGlicemia de jejum", "indication": "Rotina"}
    )
    page = scenario["dr"].get(response.url)
    assert page.context["rows"] == ["Hemograma completo", "Glicemia de jejum"]
    assert "PEDIDO DE EXAMES" in page.content.decode() and "Rotina" in page.content.decode()
    assert scenario["dr"].get(url).status_code == 403  # only the visit's author issues
    record = AuditEntry.objects.filter(model_name="Pedido de exames").latest("pk")
    assert "Hemograma" not in str(record.changes)


PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_attachments_only_pdf_jpg_png_and_only_for_practitioners(scenario):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.medical_records.models import Attachment

    visit = log_event(scenario)
    url = reverse("medical_records:attachment_upload", args=[visit.pk])
    send = lambda who, name, content: scenario[who].post(  # noqa: E731
        url, {"file": SimpleUploadedFile(name, content), "description": "Raio-X"}, follow=True
    )
    # Checked by the content, not the name: an HTML page named .png is refused.
    assert "Envie um arquivo PDF, JPG ou PNG" in send("dra", "foto.png", b"<html>").content.decode()
    large = b"%PDF-" + b"0" * (10 * 1024 * 1024)
    assert "passa de 10 MB" in send("dra", "laudo.pdf", large).content.decode()
    assert (
        scenario["reception"].post(url, {"file": SimpleUploadedFile("x.png", PNG)}).status_code
        == 403
    )

    send("dr", "raio-x paciente.png", PNG)  # another practitioner, results arrive later
    with use_clinic(scenario["clinic"]):
        attachment = Attachment.objects.get()
    assert (attachment.kind, attachment.size, attachment.practitioner.name) == (
        "image/png",
        len(PNG),
        "Dr. Bruno",
    )

    file = scenario["dra"].get(reverse("medical_records:attachment", args=[attachment.pk]))
    assert file.content == PNG and file["Content-Type"] == "image/png"
    assert file["Cache-Control"] == "private, no-store"
    assert (
        scenario["reception"]
        .get(reverse("medical_records:attachment", args=[attachment.pk]))
        .status_code
        == 403
    )
    assert "raio-x" not in str(
        list(AuditEntry.objects.filter(model_name="Anexo").values_list("object_repr", "changes"))
    )


def test_attachment_removed_only_by_uploader_before_finalizing(scenario):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.medical_records.models import Attachment

    visit = log_event(scenario)
    url = reverse("medical_records:attachment_upload", args=[visit.pk])
    scenario["dra"].post(url, {"file": SimpleUploadedFile("a.png", PNG)})
    scenario["dra"].post(url, {"file": SimpleUploadedFile("b.png", PNG)})
    with use_clinic(scenario["clinic"]):
        first, second_one = Attachment.objects.order_by("pk")
    remove_ = lambda attachment: reverse("medical_records:attachment_remove", args=[attachment.pk])  # noqa: E731
    assert scenario["dr"].post(remove_(first)).status_code == 403
    scenario["dra"].post(remove_(first))
    scenario["dra"].post(
        reverse("medical_records:visit", args=[visit.pk]), {**ANAMNESIS, "action": "finalize"}
    )
    assert scenario["dra"].post(remove_(second_one)).status_code == 403
    with use_clinic(scenario["clinic"]):
        assert list(Attachment.objects.values_list("pk", flat=True)) == [second_one.pk]


def test_system_admin_sees_and_does_everything(scenario, django_user_model):
    """The superuser writes on behalf of a chosen practitioner and edits anyone's draft."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.medical_records.models import Attachment, Certificate

    root = user_client(django_user_model.objects.create_superuser("root", password="x-12345678"))
    new_visit = reverse("medical_records:new", args=[scenario["patient"].pk])
    assert 'name="practitioner"' in root.get(new_visit).content.decode()
    response = root.post(new_visit, {**ANAMNESIS, "practitioner": scenario["ana"].pk})
    assert response.status_code == 302
    with use_clinic(scenario["clinic"]):
        visit = Visit.objects.get()
    assert visit.practitioner == scenario["ana"]
    assert visit.created_by.username == "root"  # the audit keeps who really wrote it

    # Another practitioner's draft (Dra. Ana's) can be edited by the superuser only.
    url = reverse("medical_records:visit", args=[visit.pk])
    assert scenario["dr"].post(url, {**ANAMNESIS, "plan": "x"}).status_code == 403
    assert root.post(url, {**ANAMNESIS, "plan": "Retorno em 15 dias"}).status_code == 302
    attachment_url = reverse("medical_records:attachment_upload", args=[visit.pk])
    scenario["dra"].post(
        attachment_url, {"file": SimpleUploadedFile("x.png", PNG), "description": "Foto"}
    )
    with use_clinic(scenario["clinic"]):
        attachment = Attachment.objects.get()
    assert (
        root.post(reverse("medical_records:attachment_remove", args=[attachment.pk])).status_code
        == 302
    )

    root.post(url, {**ANAMNESIS, "action": "finalize"})
    response = root.post(
        reverse("medical_records:certificate_new", args=[visit.pk]),
        {
            "kind": "attendance",
            "date": "2031-03-05",
            "start_time": "10:00",
            "end_time": "11:00",
        },
    )
    assert response.status_code == 302
    with use_clinic(scenario["clinic"]):
        assert Certificate.objects.get().practitioner == scenario["ana"]
        assert not Attachment.objects.exists()
    root.post(reverse("medical_records:addendum", args=[visit.pk]), {"text": "Correção"})
    with use_clinic(scenario["clinic"]):
        assert visit.addenda.get().practitioner == scenario["ana"]
