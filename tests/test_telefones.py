"""Phones with a valid area code and the ninth mobile digit, so WhatsApp links work
(owner: "coloque o DDD, porque o whats não funciona se não tiver certo")."""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from faker import Faker

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.core.templatetags.formatos import whatsapp
from apps.core.validadores import nono_digito, normalizar_telefone
from apps.legado.anonimizacao import _mesmo_tamanho
from apps.pacientes.models import Paciente


@pytest.mark.parametrize(
    ("digitado", "esperado"),
    [
        ("(54) 99123-4567", "54991234567"),
        ("54 9123-4567", "54991234567"),  # old 8-digit mobile gets the ninth digit
        ("(54) 3461-3354", "5434613354"),  # landline stays with 8 digits
        ("054 3461-3354", "5434613354"),  # carrier prefix 0
        ("+55 54 99123-4567", "54991234567"),  # country code
        ("", ""),
    ],
)
def test_normalizar_telefone(digitado, esperado):
    assert normalizar_telefone(digitado) == esperado


@pytest.mark.parametrize("digitado", ["(20) 3461-3354", "(54) 3123-45678", "123", "5491234"])
def test_telefone_invalido(digitado):
    with pytest.raises(ValidationError):
        normalizar_telefone(digitado)


def test_nono_digito_so_em_celular():
    assert nono_digito("5481234567") == "54981234567"
    assert nono_digito("5434613354") == "5434613354"
    assert nono_digito("99998888") == "99998888"  # no area code: left as it was


def test_link_do_whatsapp_com_ddd_e_nono_digito():
    assert whatsapp("54991234567") == "https://wa.me/5554991234567"


@pytest.mark.django_db
def test_cadastro_do_paciente_corrige_o_celular(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("recepcao_fones", clinica_a, Papel.RECEPCAO))
    resposta = cliente.post(
        reverse("pacientes:novo"),
        {
            "tipo": "PF",
            "nome": "Paciente Fictício",
            "telefone_celular": "(54) 8123-4567",
            "whatsapp": "54 8123-4567",
            "telefone_residencial": "(54) 3461-3354",
        },
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.get()
    assert (paciente.telefone_celular, paciente.whatsapp, paciente.telefone_residencial) == (
        "54981234567",
        "54981234567",
        "5434613354",
    )
    errado = cliente.post(
        reverse("pacientes:novo"), {"tipo": "PF", "nome": "Outro", "whatsapp": "(20) 98123-4567"}
    )
    assert "whatsapp" in errado.context["form"].errors


def test_anonimizacao_mantem_celular_e_fixo_validos():
    fake = Faker("pt_BR")
    for _ in range(50):
        celular = _mesmo_tamanho("5484123456", fake)  # old mobile without the ninth digit
        fixo = _mesmo_tamanho("5434613354", fake)
        assert len(celular) == 11 and celular.startswith("549")
        assert len(fixo) == 10 and fixo.startswith("54") and fixo[2] in "2345"
