"""Related people of a patient: relatives and contacts (decision 101). Fictitious data only."""

import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse

from apps.auditoria.models import RegistroAuditoria
from apps.auditoria.registro import nome_do_modelo
from apps.core.isolamento import ClinicaDiferente, sem_isolamento, usar_clinica
from apps.core.models import Papel
from apps.pacientes.models import Paciente, PessoaRelacionada

pytestmark = pytest.mark.django_db

MAE = PessoaRelacionada.Vinculo.MAE


@pytest.fixture
def recepcao(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("recepcao_relacionados", clinica_a, Papel.RECEPCAO))


@pytest.fixture
def familia(clinica_a):
    with usar_clinica(clinica_a):
        filha = Paciente.objects.create(nome="Ana Fictícia")
        mae = Paciente.objects.create(nome="Rosa Fictícia", whatsapp="54999990001")
        return filha, mae


def test_vinculo_com_outro_paciente_aparece_nas_duas_fichas(clinica_a, familia, recepcao):
    filha, mae = familia
    resposta = recepcao.post(
        reverse("pacientes:relacionado_novo", args=[filha.pk]),
        {"vinculo": MAE, "outro_paciente": mae.pk, "nome": "", "telefone": "", "observacao": ""},
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        vinculo = PessoaRelacionada.objects.get()
    assert vinculo.telefone_exibido == "54999990001"  # the other patient's own phone
    ficha_filha = recepcao.get(reverse("pacientes:ficha", args=[filha.pk])).content.decode()
    assert "Mãe:" in ficha_filha and "Rosa Fictícia" in ficha_filha
    ficha_mae = recepcao.get(reverse("pacientes:ficha", args=[mae.pk])).content.decode()
    assert "Mãe de" in ficha_mae and "Ana Fictícia" in ficha_mae


def test_contato_de_fora_da_clinica_com_telefone(clinica_a, familia, recepcao):
    filha, _ = familia
    url = reverse("pacientes:relacionado_novo", args=[filha.pk])
    dados = {
        "vinculo": PessoaRelacionada.Vinculo.EMERGENCIA,
        "outro_paciente": "",
        "nome": "Contato Inventado",
        "telefone": "(54) 99999-0002",
        "observacao": "Vizinha",
    }
    assert recepcao.post(url, dados).status_code == 302
    with usar_clinica(clinica_a):
        contato = PessoaRelacionada.objects.get()
    assert (contato.telefone, contato.nome_exibido) == ("54999990002", "Contato Inventado")
    impressa = recepcao.get(reverse("pacientes:imprimir", args=[filha.pk])).content.decode()
    assert "Contato Inventado" in impressa and "Contato de emergência" in impressa
    # Editing and removing.
    editar = reverse("pacientes:relacionado_editar", args=[contato.pk])
    assert recepcao.post(editar, {**dados, "observacao": "Tia"}).status_code == 302
    contato.refresh_from_db()
    assert contato.observacao == "Tia"
    assert (
        recepcao.get(reverse("pacientes:relacionado_remover", args=[contato.pk])).status_code == 302
    )
    remover = recepcao.post(reverse("pacientes:relacionado_remover", args=[contato.pk]))
    assert remover.status_code == 302
    assert not PessoaRelacionada.todos.exists()


@pytest.mark.parametrize(
    ("dados", "campo"),
    [
        ({"nome": "", "outro_paciente": ""}, "nome"),
        ({"nome": "Alguém", "outro_paciente": "MAE"}, "nome"),
        ({"nome": "Alguém", "telefone": "123"}, "telefone"),
        ({"nome": "", "outro_paciente": "PROPRIO"}, "outro_paciente"),
    ],
)
def test_validacoes(dados, campo, familia, recepcao):
    filha, mae = familia
    trocas = {"MAE": mae.pk, "PROPRIO": filha.pk}
    dados = {k: trocas.get(v, v) for k, v in dados.items()}
    resposta = recepcao.post(
        reverse("pacientes:relacionado_novo", args=[filha.pk]), {"vinculo": MAE, **dados}
    )
    assert campo in resposta.context["form"].errors


def test_vinculo_repetido(clinica_a, familia, recepcao):
    filha, mae = familia
    with usar_clinica(clinica_a):
        PessoaRelacionada.objects.create(paciente=filha, outro_paciente=mae, vinculo=MAE)
    resposta = recepcao.post(
        reverse("pacientes:relacionado_novo", args=[filha.pk]),
        {"vinculo": MAE, "outro_paciente": mae.pk},
    )
    assert "outro_paciente" in resposta.context["form"].errors


def test_banco_exige_paciente_ou_nome(clinica_a, familia):
    filha, _ = familia
    with usar_clinica(clinica_a), pytest.raises(IntegrityError), transaction.atomic():
        PessoaRelacionada.objects.create(paciente=filha, vinculo=MAE)


def test_nao_liga_pacientes_de_clinicas_diferentes(clinica_a, clinica_b, familia):
    filha, _ = familia
    with usar_clinica(clinica_b):
        outra = Paciente.objects.create(nome="De outra clínica")
    with sem_isolamento(), pytest.raises(ClinicaDiferente):
        PessoaRelacionada(paciente=filha, outro_paciente=outra, vinculo=MAE).save()


def test_outra_clinica_nao_ve_nem_altera(clinica_a, clinica_b, familia, criar_usuario, cliente_de):
    filha, _ = familia
    with usar_clinica(clinica_a):
        contato = PessoaRelacionada.objects.create(paciente=filha, vinculo=MAE, nome="Fictícia")
    intruso = cliente_de(criar_usuario("recepcao_b_rel", clinica_b, Papel.RECEPCAO))
    assert (
        intruso.get(reverse("pacientes:relacionado_editar", args=[contato.pk])).status_code == 404
    )
    assert intruso.get(reverse("pacientes:relacionado_novo", args=[filha.pk])).status_code == 404


def test_financeiro_so_ve(clinica_a, familia, criar_usuario, cliente_de):
    filha, _ = familia
    financeiro = cliente_de(criar_usuario("fin_rel", clinica_a, Papel.FINANCEIRO))
    ficha = financeiro.get(reverse("pacientes:ficha", args=[filha.pk])).content.decode()
    assert "Pessoas relacionadas" in ficha
    assert reverse("pacientes:relacionado_novo", args=[filha.pk]) not in ficha
    novo = financeiro.get(reverse("pacientes:relacionado_novo", args=[filha.pk]))
    assert novo.status_code == 403


def test_exclusao_lgpd_apaga_os_vinculos_dos_dois_lados(
    clinica_a, familia, criar_usuario, cliente_de
):
    filha, mae = familia
    with usar_clinica(clinica_a):
        de_filha = PessoaRelacionada.objects.create(
            paciente=filha, vinculo=PessoaRelacionada.Vinculo.EMERGENCIA, nome="NOME-SIGILOSO"
        )
        PessoaRelacionada.objects.create(paciente=mae, outro_paciente=filha, vinculo=MAE)
        filha.arquivado = True
        filha.save()
    admin = cliente_de(criar_usuario("admin_rel", clinica_a, Papel.ADMIN))
    assert admin.post(reverse("pacientes:excluir", args=[filha.pk])).status_code == 302
    assert not PessoaRelacionada.todos.exists()
    registros = RegistroAuditoria.objects.filter(
        modelo=nome_do_modelo(PessoaRelacionada), objeto_id=str(de_filha.pk)
    )
    assert registros.exists()
    assert "NOME-SIGILOSO" not in str(list(registros.values()))
