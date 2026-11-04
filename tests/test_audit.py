import datetime

import pytest
from axes.models import AccessAttempt
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db
Acao = AuditEntry.Acao


@pytest.fixture
def admin_a(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))


def ultimos(**filtros):
    return list(AuditEntry.objects.filter(**filtros).order_by("pk"))


def test_criacao_alteracao_e_exclusao_ficam_registradas(admin_a, clinica_a):
    admin_a.post(reverse("patients:new"), {"kind": "PF", "name": "Maria", "active": "on"})
    with usar_clinica(clinica_a):
        patient = Patient.objects.get(name="Maria")
    [criacao] = ultimos(acao=Acao.CRIAR, modelo="Paciente")
    assert criacao.usuario_nome == "admin_a"
    assert criacao.clinic_id == clinica_a.pk
    assert criacao.objeto_id == str(patient.pk)
    assert criacao.alteracoes["name"] == [None, "Maria"]
    assert criacao.ip == "127.0.0.1"

    admin_a.post(
        reverse("patients:edit", args=[patient.pk]),
        {"kind": "PF", "name": "Maria Souza", "active": "on", "occupation": "Professora"},
    )
    [alteracao] = ultimos(acao=Acao.ALTERAR, modelo="Paciente")
    assert alteracao.alteracoes == {
        "name": ["Maria", "Maria Souza"],
        "occupation": ["", "Professora"],
    }

    admin_a.post(reverse("patients:archive", args=[patient.pk]))
    [arquivamento] = ultimos(acao=Acao.ALTERAR, modelo="Paciente")[1:]
    assert arquivamento.alteracoes["archived"] == [False, True]


def test_exclusao_definitiva_tira_os_dados_pessoais_da_auditoria(admin_a, clinica_a):
    admin_a.post(
        reverse("patients:new"),
        {"kind": "PF", "name": "Maria Sigilosa", "active": "on", "tax_id": "52998224725"},
    )
    with usar_clinica(clinica_a):
        patient = Patient.objects.get(name="Maria Sigilosa")
    admin_a.get(reverse("patients:record", args=[patient.pk]))
    admin_a.post(reverse("patients:archive", args=[patient.pk]))
    admin_a.post(reverse("patients:delete", args=[patient.pk]))

    registros = ultimos(modelo="Paciente", objeto_id=str(patient.pk))
    assert {r.acao for r in registros} == {Acao.CRIAR, Acao.VISUALIZAR, Acao.ALTERAR, Acao.EXCLUIR}
    texto = str([(r.objeto_descricao, r.alteracoes, r.usuario_nome) for r in registros])
    assert "Sigilosa" not in texto and "52998224725" not in texto
    assert "admin_a" in texto  # who did it stays
    criacao = next(r for r in registros if r.acao == Acao.CRIAR)
    assert criacao.alteracoes["name"] == ["(removido)", "(removido)"]
    assert ultimos(objeto_descricao__contains="excluídos a pedido do titular")
    # The erasure shows in the clinic's own audit log (review stage 4).
    pagina = admin_a.get(reverse("audit:list")).content.decode()
    assert f"Paciente {patient.pk}: dados pessoais excluídos a pedido do titular" in pagina


def test_salvar_sem_mudancas_nao_gera_registro(clinica_a):
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(name="Sem mudança")
        patient.save()
    assert not ultimos(acao=Acao.ALTERAR, modelo="Paciente")


def test_abrir_a_ficha_fica_registrado(admin_a, clinica_a):
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(name="Consultado")
    admin_a.get(reverse("patients:record", args=[patient.pk]))
    [visualizacao] = ultimos(acao=Acao.VISUALIZAR)
    assert visualizacao.objeto_descricao == "Consultado"
    assert visualizacao.usuario_nome == "admin_a"


def test_login_e_tentativa_recusada_ficam_registrados(client, criar_usuario):
    criar_usuario("maria")
    client.post(reverse("login"), {"username": "maria", "password": "errada"})
    [falha] = ultimos(acao=Acao.LOGIN_FALHOU)
    assert falha.objeto_descricao == "usuário informado: maria"
    assert "errada" not in str(falha.alteracoes) + falha.objeto_descricao

    client.post(reverse("login"), {"username": "maria", "password": "senha-de-teste-123"})
    [entrada] = ultimos(acao=Acao.LOGIN)
    assert entrada.usuario_nome == "maria"


def test_senha_nunca_e_gravada(criar_usuario):
    user = criar_usuario("joao")
    user.set_password("nova-senha-secreta-123")
    user.save()
    registros = AuditEntry.objects.filter(modelo="Usuário")
    texto = " ".join(str(r.alteracoes) for r in registros)
    assert "argon2" not in texto and "nova-senha" not in texto
    [alteracao] = registros.filter(acao=Acao.ALTERAR)
    assert alteracao.alteracoes == {"senha": ["(oculta)", "(alterada)"]}


def test_tela_mostra_somente_a_clinica_atual(admin_a, clinica_a, clinica_b):
    with usar_clinica(clinica_a):
        Patient.objects.create(name="Paciente da A")
    with usar_clinica(clinica_b):
        Patient.objects.create(name="Paciente da B")
    conteudo = admin_a.get(reverse("audit:list"), {"modelo": "Paciente"}).content.decode()
    assert "Paciente da A" in conteudo
    assert "Paciente da B" not in conteudo


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_somente_administrador_ve_a_auditoria(papel, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario", clinica_a, papel))
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
    assert AuditEntry.objects.filter(objeto_descricao="temporario").exists()


def test_retencao_apaga_so_tentativas_recusadas_antigas():
    antigo = timezone.now() - datetime.timedelta(days=31)
    recente = timezone.now() - datetime.timedelta(days=29)
    for timestamp in (antigo, recente):
        for acao in (Acao.LOGIN_FALHOU, Acao.LOGIN):
            record = AuditEntry.objects.create(acao=acao)
            AuditEntry.objects.filter(pk=record.pk).update(timestamp=timestamp)
        tentativa = AccessAttempt.objects.create(username="quem", failures_since_start=1)
        AccessAttempt.objects.filter(pk=tentativa.pk).update(attempt_time=timestamp)

    call_command("apply_retention")

    restantes = AuditEntry.objects.values_list("acao", "timestamp")
    assert sorted(acao for acao, _ in restantes) == [Acao.LOGIN, Acao.LOGIN, Acao.LOGIN_FALHOU]
    assert all(m == recente for acao, m in restantes if acao == Acao.LOGIN_FALHOU)
    assert list(AccessAttempt.objects.values_list("attempt_time", flat=True)) == [recente]


def test_tela_mostra_o_rotulo_do_campo_tambem_pelo_nome_antigo(admin_a, clinica_a):
    """Decision 156: the page shows the field's label, not its name in the code, so renaming a
    field (or its column-keeping rename) does not change what the clinic reads."""
    from apps.audit.models import AuditEntry

    admin_a.post(reverse("patients:new"), {"kind": "PF", "name": "Maria", "active": "on"})
    AuditEntry.objects.create(
        clinic=clinica_a,
        acao=Acao.ALTERAR,
        modelo="Paciente",
        objeto_id="1",
        alteracoes={"occupation": ["", "Professora"], "campo_que_saiu": [1, 2]},
    )
    pagina = admin_a.get(reverse("audit:list")).content.decode()
    assert "<strong>nome</strong>: — → Maria" in pagina
    assert "<strong>profissão</strong>:  → Professora" in pagina
    assert "<strong>campo_que_saiu</strong>: 1 → 2" in pagina
