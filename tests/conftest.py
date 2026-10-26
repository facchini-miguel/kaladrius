import pytest

from apps.core.isolamento import usar_clinica
from apps.core.models import Clinica, Papel, Vinculo
from apps.profissionais.models import Profissional

SENHA = "senha-de-teste-123"


@pytest.fixture
def clinica_a(db):
    return Clinica.objects.create(nome="Clínica A")


@pytest.fixture
def clinica_b(db):
    return Clinica.objects.create(nome="Clínica B")


@pytest.fixture
def criar_usuario(django_user_model):
    """Create a user, optionally linked to a clinic with a role."""

    def criar(username, clinica=None, papel=Papel.RECEPCAO, **extra):
        usuario = django_user_model.objects.create_user(username=username, password=SENHA, **extra)
        if clinica is not None:
            Vinculo.objects.create(usuario=usuario, clinica=clinica, papel=papel)
        return usuario

    return criar


@pytest.fixture
def criar_profissional():
    """Create a practitioner inside the given clinic."""

    def criar(clinica, nome, **extra):
        with usar_clinica(clinica):
            return Profissional.objects.create(nome=nome, **extra)

    return criar


@pytest.fixture
def cliente_de(client):
    """Log the test client in as the given user."""

    def entrar(usuario):
        client.force_login(usuario)
        return client

    return entrar
