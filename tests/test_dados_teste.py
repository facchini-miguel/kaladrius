import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db.models import F

from apps.agenda.models import Agendamento
from apps.auditoria.models import RegistroAuditoria
from apps.core.isolamento import sem_isolamento
from apps.core.models import Clinica, Vinculo
from apps.core.validadores import cnpj_valido, cpf_valido
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada

pytestmark = pytest.mark.django_db


def test_popular_dados_teste_e_idempotente(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    call_command("popular_dados_teste", pacientes=30)
    call_command("popular_dados_teste", pacientes=30)

    # One installation, one clinic (decision 069).
    assert Clinica.objects.count() == 1
    assert get_user_model().objects.get(username="dr.carlos").check_password("senha-de-teste-123")
    assert Vinculo.objects.filter(usuario__username="dra.ana").count() == 1
    with sem_isolamento():
        assert Profissional.objects.count() == 5
        assert Profissional.objects.get(nome="Dra. Ana Souza").usuario.username == "dra.ana"
        assert Paciente.objects.count() == 30  # not duplicated on the 2nd run
        assert Paciente.objects.filter(tipo=Paciente.Tipo.JURIDICA).count() == 1
        for paciente in Paciente.objects.exclude(cpf_cnpj=""):
            valido = cpf_valido if paciente.tipo == Paciente.Tipo.FISICA else cnpj_valido
            assert valido(paciente.cpf_cnpj), paciente.cpf_cnpj
        assert not Paciente.objects.exclude(email__endswith="@example.com").exists()
        assert Agendamento.objects.count() > 0  # created once, not duplicated
        assert Rechamada.objects.count() == 80  # not duplicated
        assert Agendamento.objects.filter(profissional__clinica=F("clinica")).count() == (
            Agendamento.objects.count()
        )


def test_popular_dados_teste_exige_debug(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    with pytest.raises(CommandError):
        call_command("popular_dados_teste")


def test_remover_dados_teste_nao_toca_nos_dados_reais(settings, monkeypatch, criar_usuario):
    settings.DEBUG = True
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    call_command("popular_dados_teste", pacientes=5)
    real = Clinica.objects.create(nome="Clínica Real")
    criar_usuario("pessoa.real", real)
    # A test username that also works in a real clinic is kept.
    Vinculo.objects.create(usuario=get_user_model().objects.get(username="dra.ana"), clinica=real)
    with sem_isolamento():
        Paciente.objects.create(clinica=real, nome="Paciente Real")

    with pytest.raises(CommandError):
        call_command("remover_dados_teste")
    call_command("remover_dados_teste", confirmar=True)

    assert list(Clinica.objects.values_list("nome", flat=True)) == ["Clínica Real"]
    restantes = set(get_user_model().objects.values_list("username", flat=True))
    assert restantes == {"pessoa.real", "dra.ana"}
    with sem_isolamento():
        assert list(Paciente.objects.values_list("nome", flat=True)) == ["Paciente Real"]
        assert not Agendamento.objects.exists() and not Rechamada.objects.exists()
        assert set(Profissional.objects.values_list("clinica", flat=True)) <= {real.pk}
    assert not RegistroAuditoria.objects.filter(objeto_descricao__contains="(teste)").exists()
    assert RegistroAuditoria.objects.filter(
        objeto_descricao__startswith="Dados de teste removidos: 1 clínicas"
    ).exists()
