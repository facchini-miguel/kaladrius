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
def admin_a(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_a", clinica_a, Role.ADMIN))


def ultimos(**filters):
    return list(AuditEntry.objects.filter(**filters).order_by("pk"))


def test_criacao_alteracao_e_exclusao_ficam_registradas(admin_a, clinica_a):
    admin_a.post(reverse("patients:new"), {"kind": "PF", "name": "Maria", "active": "on"})
    with use_clinic(clinica_a):
        patient = Patient.objects.get(name="Maria")
    [criacao] = ultimos(action=Action.CREATE, model_name="Paciente")
    assert criacao.user_name == "admin_a"
    assert criacao.clinic_id == clinica_a.pk
    assert criacao.object_id == str(patient.pk)
    assert criacao.changes["name"] == [None, "Maria"]
    assert criacao.ip == "127.0.0.1"

    admin_a.post(
        reverse("patients:edit", args=[patient.pk]),
        {"kind": "PF", "name": "Maria Souza", "active": "on", "occupation": "Professora"},
    )
    [alteracao] = ultimos(action=Action.CHANGE, model_name="Paciente")
    assert alteracao.changes == {
        "name": ["Maria", "Maria Souza"],
        "occupation": ["", "Professora"],
    }

    admin_a.post(reverse("patients:archive", args=[patient.pk]))
    [arquivamento] = ultimos(action=Action.CHANGE, model_name="Paciente")[1:]
    assert arquivamento.changes["archived"] == [False, True]


def test_exclusao_definitiva_tira_os_dados_pessoais_da_auditoria(admin_a, clinica_a):
    admin_a.post(
        reverse("patients:new"),
        {"kind": "PF", "name": "Maria Sigilosa", "active": "on", "tax_id": "52998224725"},
    )
    with use_clinic(clinica_a):
        patient = Patient.objects.get(name="Maria Sigilosa")
    admin_a.get(reverse("patients:record", args=[patient.pk]))
    admin_a.post(reverse("patients:archive", args=[patient.pk]))
    admin_a.post(reverse("patients:delete", args=[patient.pk]))

    registros = ultimos(model_name="Paciente", object_id=str(patient.pk))
    assert {r.action for r in registros} == {
        Action.CREATE,
        Action.VIEWED,
        Action.CHANGE,
        Action.DELETE,
    }
    text = str([(r.object_repr, r.changes, r.user_name) for r in registros])
    assert "Sigilosa" not in text and "52998224725" not in text
    assert "admin_a" in text  # who did it stays
    criacao = next(r for r in registros if r.action == Action.CREATE)
    assert criacao.changes["name"] == ["(removido)", "(removido)"]
    assert ultimos(object_repr__contains="excluídos a pedido do titular")
    # The erasure shows in the clinic's own audit log (review stage 4).
    page = admin_a.get(reverse("audit:list")).content.decode()
    assert f"Paciente {patient.pk}: dados pessoais excluídos a pedido do titular" in page


def test_salvar_sem_mudancas_nao_gera_registro(clinica_a):
    with use_clinic(clinica_a):
        patient = Patient.objects.create(name="Sem mudança")
        patient.save()
    assert not ultimos(action=Action.CHANGE, model_name="Paciente")


def test_abrir_a_ficha_fica_registrado(admin_a, clinica_a):
    with use_clinic(clinica_a):
        patient = Patient.objects.create(name="Consultado")
    admin_a.get(reverse("patients:record", args=[patient.pk]))
    [visualizacao] = ultimos(action=Action.VIEWED)
    assert visualizacao.object_repr == "Consultado"
    assert visualizacao.user_name == "admin_a"


def test_login_e_tentativa_recusada_ficam_registrados(client, criar_usuario):
    criar_usuario("maria")
    client.post(reverse("login"), {"username": "maria", "password": "errada"})
    [falha] = ultimos(action=Action.LOGIN_FAILED)
    assert falha.object_repr == "usuário informado: maria"
    assert "errada" not in str(falha.changes) + falha.object_repr

    client.post(reverse("login"), {"username": "maria", "password": "senha-de-teste-123"})
    [entrada] = ultimos(action=Action.LOGIN)
    assert entrada.user_name == "maria"


def test_senha_nunca_e_gravada(criar_usuario):
    user = criar_usuario("joao")
    user.set_password("nova-senha-secreta-123")
    user.save()
    registros = AuditEntry.objects.filter(model_name="Usuário")
    text = " ".join(str(r.changes) for r in registros)
    assert "argon2" not in text and "nova-senha" not in text
    [alteracao] = registros.filter(action=Action.CHANGE)
    assert alteracao.changes == {"senha": ["(oculta)", "(alterada)"]}


def test_tela_mostra_somente_a_clinica_atual(admin_a, clinica_a, clinica_b):
    with use_clinic(clinica_a):
        Patient.objects.create(name="Paciente da A")
    with use_clinic(clinica_b):
        Patient.objects.create(name="Paciente da B")
    content = admin_a.get(reverse("audit:list"), {"model_name": "Paciente"}).content.decode()
    assert "Paciente da A" in content
    assert "Paciente da B" not in content


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.PRACTITIONER])
def test_somente_administrador_ve_a_auditoria(role, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario", clinica_a, role))
    assert cliente.get(reverse("audit:list")).status_code == 403
    assert "Auditoria" not in cliente.get(reverse("home")).content.decode()


def test_admin_do_django_e_somente_leitura(django_user_model, client):
    root = django_user_model.objects.create_superuser("root", password="senha-de-teste-123")
    client.force_login(root)
    assert client.get(reverse("admin:auditoria_auditentry_changelist")).status_code == 200
    assert client.get(reverse("admin:auditoria_auditentry_add")).status_code == 403


def test_exclusao_de_usuario_mantem_o_historico(criar_usuario):
    user = criar_usuario("temporario")
    user.delete()
    assert AuditEntry.objects.filter(object_repr="temporario").exists()


def test_retencao_apaga_so_tentativas_recusadas_antigas():
    old = timezone.now() - datetime.timedelta(days=31)
    recente = timezone.now() - datetime.timedelta(days=29)
    for timestamp in (old, recente):
        for action in (Action.LOGIN_FAILED, Action.LOGIN):
            record = AuditEntry.objects.create(action=action)
            AuditEntry.objects.filter(pk=record.pk).update(timestamp=timestamp)
        tentativa = AccessAttempt.objects.create(username="quem", failures_since_start=1)
        AccessAttempt.objects.filter(pk=tentativa.pk).update(attempt_time=timestamp)

    call_command("apply_retention")

    restantes = AuditEntry.objects.values_list("action", "timestamp")
    assert sorted(action for action, _ in restantes) == [
        Action.LOGIN,
        Action.LOGIN,
        Action.LOGIN_FAILED,
    ]
    assert all(m == recente for action, m in restantes if action == Action.LOGIN_FAILED)
    assert list(AccessAttempt.objects.values_list("attempt_time", flat=True)) == [recente]


def test_tela_mostra_o_rotulo_do_campo_tambem_pelo_nome_antigo(admin_a, clinica_a):
    """Decision 156: the page shows the field's label, not its name in the code, so renaming a
    field (or its column-keeping rename) does not change what the clinic reads."""
    from apps.audit.models import AuditEntry

    admin_a.post(reverse("patients:new"), {"kind": "PF", "name": "Maria", "active": "on"})
    AuditEntry.objects.create(
        clinic=clinica_a,
        action=Action.CHANGE,
        model_name="Paciente",
        object_id="1",
        changes={"occupation": ["", "Professora"], "campo_que_saiu": [1, 2]},
    )
    page = admin_a.get(reverse("audit:list")).content.decode()
    assert "<strong>nome</strong>: — → Maria" in page
    assert "<strong>profissão</strong>:  → Professora" in page
    assert "<strong>campo_que_saiu</strong>: 1 → 2" in page
