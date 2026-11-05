"""Related people of a patient: relatives and contacts (decision 101). Fictitious data only."""

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.audit.models import AuditEntry
from apps.audit.record import nome_do_modelo
from apps.core.isolation import ClinicaDiferente, sem_isolamento, usar_clinica
from apps.core.models import Papel
from apps.patients.models import Patient, RelatedPerson

pytestmark = pytest.mark.django_db

MAE = RelatedPerson.Relationship.MAE


@pytest.fixture
def reception(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("recepcao_relacionados", clinica_a, Papel.RECEPCAO))


@pytest.fixture
def familia(clinica_a):
    with usar_clinica(clinica_a):
        filha = Patient.objects.create(name="Ana Fictícia")
        mae = Patient.objects.create(name="Rosa Fictícia", whatsapp="54999990001")
        return filha, mae


def test_vinculo_com_outro_paciente_aparece_nas_duas_fichas(clinica_a, familia, reception):
    filha, mae = familia
    response = reception.post(
        reverse("patients:related_new", args=[filha.pk]),
        {"relationship": MAE, "other_patient": mae.pk, "name": "", "phone": "", "note": ""},
    )
    assert response.status_code == 302
    with usar_clinica(clinica_a):
        vinculo = RelatedPerson.objects.get()
    assert vinculo.telefone_exibido == "54999990001"  # the other patient's own phone
    ficha_filha = reception.get(reverse("patients:record", args=[filha.pk])).content.decode()
    assert "Mãe:" in ficha_filha and "Rosa Fictícia" in ficha_filha
    ficha_mae = reception.get(reverse("patients:record", args=[mae.pk])).content.decode()
    assert "Mãe de" in ficha_mae and "Ana Fictícia" in ficha_mae


def test_contato_de_fora_da_clinica_com_telefone(clinica_a, familia, reception):
    filha, _ = familia
    url = reverse("patients:related_new", args=[filha.pk])
    data = {
        "relationship": RelatedPerson.Relationship.EMERGENCIA,
        "other_patient": "",
        "name": "Contato Inventado",
        "phone": "(54) 99999-0002",
        "note": "Vizinha",
    }
    assert reception.post(url, data).status_code == 302
    with usar_clinica(clinica_a):
        contato = RelatedPerson.objects.get()
    assert (contato.phone, contato.nome_exibido) == ("54999990002", "Contato Inventado")
    impressa = reception.get(reverse("patients:print", args=[filha.pk])).content.decode()
    assert "Contato Inventado" in impressa and "Contato de emergência" in impressa
    # Editing and removing.
    editar = reverse("patients:related_edit", args=[contato.pk])
    assert reception.post(editar, {**data, "note": "Tia"}).status_code == 302
    contato.refresh_from_db()
    assert contato.note == "Tia"
    assert reception.get(reverse("patients:related_remove", args=[contato.pk])).status_code == 302
    remover = reception.post(reverse("patients:related_remove", args=[contato.pk]))
    assert remover.status_code == 302
    assert not RelatedPerson.todos.exists()


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"name": "", "other_patient": ""}, "name"),
        ({"name": "Alguém", "other_patient": "MAE"}, "name"),
        ({"name": "Alguém", "phone": "123"}, "phone"),
        ({"name": "", "other_patient": "PROPRIO"}, "other_patient"),
    ],
)
def test_validacoes(data, field, familia, reception):
    filha, mae = familia
    trocas = {"MAE": mae.pk, "PROPRIO": filha.pk}
    data = {k: trocas.get(v, v) for k, v in data.items()}
    response = reception.post(
        reverse("patients:related_new", args=[filha.pk]), {"relationship": MAE, **data}
    )
    assert field in response.context["form"].errors


def test_vinculo_repetido(clinica_a, familia, reception):
    filha, mae = familia
    with usar_clinica(clinica_a):
        RelatedPerson.objects.create(patient=filha, other_patient=mae, relationship=MAE)
    response = reception.post(
        reverse("patients:related_new", args=[filha.pk]),
        {"relationship": MAE, "other_patient": mae.pk},
    )
    assert "other_patient" in response.context["form"].errors


def test_banco_exige_paciente_ou_nome(clinica_a, familia):
    filha, _ = familia
    with usar_clinica(clinica_a), pytest.raises(IntegrityError), transaction.atomic():
        RelatedPerson.objects.create(patient=filha, relationship=MAE)


def test_nao_liga_pacientes_de_clinicas_diferentes(clinica_a, clinica_b, familia):
    filha, _ = familia
    with usar_clinica(clinica_b):
        outra = Patient.objects.create(name="De outra clínica")
    with sem_isolamento(), pytest.raises(ClinicaDiferente):
        RelatedPerson(patient=filha, other_patient=outra, relationship=MAE).save()


def test_outra_clinica_nao_ve_nem_altera(clinica_a, clinica_b, familia, criar_usuario, cliente_de):
    filha, _ = familia
    with usar_clinica(clinica_a):
        contato = RelatedPerson.objects.create(patient=filha, relationship=MAE, name="Fictícia")
    intruso = cliente_de(criar_usuario("recepcao_b_rel", clinica_b, Papel.RECEPCAO))
    assert intruso.get(reverse("patients:related_edit", args=[contato.pk])).status_code == 404
    assert intruso.get(reverse("patients:related_new", args=[filha.pk])).status_code == 404


def test_financeiro_so_ve(clinica_a, familia, criar_usuario, cliente_de):
    filha, _ = familia
    financeiro = cliente_de(criar_usuario("fin_rel", clinica_a, Papel.FINANCEIRO))
    ficha = financeiro.get(reverse("patients:record", args=[filha.pk])).content.decode()
    assert "Pessoas relacionadas" in ficha
    assert reverse("patients:related_new", args=[filha.pk]) not in ficha
    new = financeiro.get(reverse("patients:related_new", args=[filha.pk]))
    assert new.status_code == 403


def test_exclusao_lgpd_apaga_os_vinculos_dos_dois_lados(
    clinica_a, familia, criar_usuario, cliente_de
):
    filha, mae = familia
    with usar_clinica(clinica_a):
        de_filha = RelatedPerson.objects.create(
            patient=filha, relationship=RelatedPerson.Relationship.EMERGENCIA, name="NOME-SIGILOSO"
        )
        RelatedPerson.objects.create(patient=mae, other_patient=filha, relationship=MAE)
        filha.archived = True
        filha.save()
    admin = cliente_de(criar_usuario("admin_rel", clinica_a, Papel.ADMIN))
    assert admin.post(reverse("patients:delete", args=[filha.pk])).status_code == 302
    assert not RelatedPerson.todos.exists()
    registros = AuditEntry.objects.filter(
        model_name=nome_do_modelo(RelatedPerson), object_id=str(de_filha.pk)
    )
    assert registros.exists()
    assert "NOME-SIGILOSO" not in str(list(registros.values()))
