import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from apps.core.isolamento import sem_isolamento
from apps.core.models import Clinica, Vinculo
from apps.core.validadores import cnpj_valido, cpf_valido
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

pytestmark = pytest.mark.django_db


def test_popular_dados_teste_e_idempotente(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    call_command("popular_dados_teste", pacientes=30)
    call_command("popular_dados_teste", pacientes=30)

    assert Clinica.objects.count() == 2
    multi = get_user_model().objects.get(username="recepcao.multi")
    assert multi.vinculos.count() == 2
    assert multi.check_password("senha-de-teste-123")
    assert Vinculo.objects.filter(usuario__username="dra.ana").count() == 1
    with sem_isolamento():
        assert Profissional.objects.count() == 5
        assert Profissional.objects.get(nome="Dra. Ana Souza").usuario.username == "dra.ana"
        assert Paciente.objects.count() == 60  # 30 per clinic, not duplicated on the 2nd run
        assert Paciente.objects.filter(tipo=Paciente.Tipo.JURIDICA).count() == 2
        for paciente in Paciente.objects.exclude(cpf_cnpj=""):
            valido = cpf_valido if paciente.tipo == Paciente.Tipo.FISICA else cnpj_valido
            assert valido(paciente.cpf_cnpj), paciente.cpf_cnpj
        assert not Paciente.objects.exclude(email__endswith="@example.com").exists()


def test_popular_dados_teste_exige_debug(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    with pytest.raises(CommandError):
        call_command("popular_dados_teste")
