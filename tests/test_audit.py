import datetime

import pytest
from axes.models import AccessAttempt
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db
Action = AuditEntry.Action


@pytest.fixture
def admin_a(clinic_a, create_user, client_for):
    return client_for(create_user("admin_a", clinic_a, Role.ADMIN))


def last_ones(**filters):
    return list(AuditEntry.objects.filter(**filters).order_by("pk"))


def test_creation_change_and_deletion_are_logged(admin_a, clinic_a):
    admin_a.post(reverse("patients:new"), {"kind": "PF", "name": "Maria", "active": "on"})
    with use_clinic(clinic_a):
        patient = Patient.objects.get(name="Maria")
    [creation] = last_ones(action=Action.CREATE, model_name="Paciente")
    assert creation.user_name == "admin_a"
    assert creation.clinic_id == clinic_a.pk
    assert creation.object_id == str(patient.pk)
    assert creation.changes["name"] == [None, "Maria"]
    assert creation.ip == "127.0.0.1"

    admin_a.post(
        reverse("patients:edit", args=[patient.pk]),
        {"kind": "PF", "name": "Maria Souza", "active": "on", "occupation": "Professora"},
    )
    [change] = last_ones(action=Action.CHANGE, model_name="Paciente")
    assert change.changes == {
        "name": ["Maria", "Maria Souza"],
        "occupation": ["", "Professora"],
    }

    admin_a.post(reverse("patients:archive", args=[patient.pk]))
    [archiving] = last_ones(action=Action.CHANGE, model_name="Paciente")[1:]
    assert archiving.changes["archived"] == [False, True]


def test_permanent_deletion_removes_personal_data_from_audit(admin_a, clinic_a):
    admin_a.post(
        reverse("patients:new"),
        {"kind": "PF", "name": "Maria Sigilosa", "active": "on", "tax_id": "52998224725"},
    )
    with use_clinic(clinic_a):
        patient = Patient.objects.get(name="Maria Sigilosa")
    admin_a.get(reverse("patients:record", args=[patient.pk]))
    admin_a.post(reverse("patients:archive", args=[patient.pk]))
    admin_a.post(reverse("patients:delete", args=[patient.pk]))

    records = last_ones(model_name="Paciente", object_id=str(patient.pk))
    assert {r.action for r in records} == {
        Action.CREATE,
        Action.VIEWED,
        Action.CHANGE,
        Action.DELETE,
    }
    text = str([(r.object_repr, r.changes, r.user_name) for r in records])
    assert "Sigilosa" not in text and "52998224725" not in text
    assert "admin_a" in text  # who did it stays
    creation = next(r for r in records if r.action == Action.CREATE)
    assert creation.changes["name"] == ["(removido)", "(removido)"]
    assert last_ones(object_repr__contains="excluídos a pedido do titular")
    # The erasure shows in the clinic's own audit log (review stage 4).
    page = admin_a.get(reverse("audit:list")).content.decode()
    assert f"Paciente {patient.pk}: dados pessoais excluídos a pedido do titular" in page


def test_saving_without_changes_logs_nothing(clinic_a):
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="Sem mudança")
        patient.save()
    assert not last_ones(action=Action.CHANGE, model_name="Paciente")


def test_opening_the_record_is_logged(admin_a, clinic_a):
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="Consultado")
    admin_a.get(reverse("patients:record", args=[patient.pk]))
    [viewing] = last_ones(action=Action.VIEWED)
    assert viewing.object_repr == "Consultado"
    assert viewing.user_name == "admin_a"


def test_login_and_refused_attempt_are_logged(client, create_user):
    create_user("maria")
    client.post(reverse("login"), {"username": "maria", "password": "errada"})
    [failure] = last_ones(action=Action.LOGIN_FAILED)
    assert failure.object_repr == "usuário informado: maria"
    assert "errada" not in str(failure.changes) + failure.object_repr

    client.post(reverse("login"), {"username": "maria", "password": "senha-de-teste-123"})
    [entry_line] = last_ones(action=Action.LOGIN)
    assert entry_line.user_name == "maria"


def test_password_is_never_stored(create_user):
    user = create_user("joao")
    user.set_password("nova-senha-secreta-123")
    user.save()
    records = AuditEntry.objects.filter(model_name="Usuário")
    text = " ".join(str(r.changes) for r in records)
    assert "argon2" not in text and "nova-senha" not in text
    [change] = records.filter(action=Action.CHANGE)
    assert change.changes == {"senha": ["(oculta)", "(alterada)"]}


def test_screen_shows_only_the_current_clinic(admin_a, clinic_a, clinic_b):
    with use_clinic(clinic_a):
        Patient.objects.create(name="Paciente da A")
    with use_clinic(clinic_b):
        Patient.objects.create(name="Paciente da B")
    content = admin_a.get(reverse("audit:list"), {"model_name": "Paciente"}).content.decode()
    assert "Paciente da A" in content
    assert "Paciente da B" not in content


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.PRACTITIONER])
def test_only_admin_sees_the_audit(role, clinic_a, create_user, client_for):
    user_client = client_for(create_user("usuario", clinic_a, role))
    assert user_client.get(reverse("audit:list")).status_code == 403
    assert "Auditoria" not in user_client.get(reverse("home")).content.decode()


def test_django_admin_is_read_only(django_user_model, client):
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    client.force_login(root)
    assert client.get(reverse("admin:audit_auditentry_changelist")).status_code == 200
    assert client.get(reverse("admin:audit_auditentry_add")).status_code == 403


def test_user_deletion_keeps_the_history(create_user):
    user = create_user("temporario")
    user.delete()
    assert AuditEntry.objects.filter(object_repr="temporario").exists()


def test_retention_deletes_only_old_refused_attempts():
    old = timezone.now() - datetime.timedelta(days=31)
    recent = timezone.now() - datetime.timedelta(days=29)
    for timestamp in (old, recent):
        for action in (Action.LOGIN_FAILED, Action.LOGIN):
            record = AuditEntry.objects.create(action=action)
            AuditEntry.objects.filter(pk=record.pk).update(timestamp=timestamp)
        attempt_number = AccessAttempt.objects.create(username="quem", failures_since_start=1)
        AccessAttempt.objects.filter(pk=attempt_number.pk).update(attempt_time=timestamp)

    call_command("apply_retention")

    remaining = AuditEntry.objects.values_list("action", "timestamp")
    assert sorted(action for action, _ in remaining) == [
        Action.LOGIN,
        Action.LOGIN,
        Action.LOGIN_FAILED,
    ]
    assert all(m == recent for action, m in remaining if action == Action.LOGIN_FAILED)
    assert list(AccessAttempt.objects.values_list("attempt_time", flat=True)) == [recent]


def test_screen_shows_field_label_also_by_old_name(admin_a, clinic_a):
    """Decision 156: the page shows the field's label, not its name in the code, so renaming a
    field (or its column-keeping rename) does not change what the clinic reads."""
    from apps.audit.models import AuditEntry

    admin_a.post(reverse("patients:new"), {"kind": "PF", "name": "Maria", "active": "on"})
    AuditEntry.objects.create(
        clinic=clinic_a,
        action=Action.CHANGE,
        model_name="Paciente",
        object_id="1",
        changes={"occupation": ["", "Professora"], "campo_que_saiu": [1, 2]},
    )
    page = admin_a.get(reverse("audit:list")).content.decode()
    assert "<strong>nome</strong>: — → Maria" in page
    assert "<strong>profissão</strong>:  → Professora" in page
    assert "<strong>campo_que_saiu</strong>: 1 → 2" in page
