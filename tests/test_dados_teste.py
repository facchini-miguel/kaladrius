import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command

from apps.core.isolamento import sem_isolamento
from apps.core.models import Clinica, Vinculo
from apps.profissionais.models import Profissional

pytestmark = pytest.mark.django_db


def test_popular_dados_teste_e_idempotente(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    call_command("popular_dados_teste")
    call_command("popular_dados_teste")

    assert Clinica.objects.count() == 2
    multi = get_user_model().objects.get(username="recepcao.multi")
    assert multi.vinculos.count() == 2
    assert multi.check_password("senha-de-teste-123")
    assert Vinculo.objects.filter(usuario__username="dra.ana").count() == 1
    with sem_isolamento():
        assert Profissional.objects.count() == 5
        assert Profissional.objects.get(nome="Dra. Ana Souza").usuario.username == "dra.ana"


def test_popular_dados_teste_exige_debug(settings, monkeypatch):
    settings.DEBUG = False
    monkeypatch.setenv("DJANGO_SEED_PASSWORD", "senha-de-teste-123")
    with pytest.raises(CommandError):
        call_command("popular_dados_teste")
