import pytest

from apps.core.isolation import usar_clinica
from apps.core.models import Clinic, Membership, Papel
from apps.practitioners.models import Practitioner

SENHA = "senha-de-teste-123"


@pytest.fixture
def clinica_a(db):
    return Clinic.objects.create(nome="Clínica A")


@pytest.fixture
def clinica_b(db):
    return Clinic.objects.create(nome="Clínica B")


@pytest.fixture
def criar_usuario(django_user_model):
    """Create a user, optionally linked to a clinic with a role."""

    def criar(username, clinic=None, papel=Papel.RECEPCAO, **extra):
        usuario = django_user_model.objects.create_user(username=username, password=SENHA, **extra)
        if clinic is not None:
            Membership.objects.create(usuario=usuario, clinic=clinic, papel=papel)
        return usuario

    return criar


@pytest.fixture
def criar_profissional():
    """Create a practitioner inside the given clinic."""

    def criar(clinic, nome, **extra):
        with usar_clinica(clinic):
            return Practitioner.objects.create(nome=nome, **extra)

    return criar


@pytest.fixture
def cliente_de(client):
    """Log the test client in as the given user."""

    def entrar(usuario):
        client.force_login(usuario)
        return client

    return entrar


def pytest_sessionstart(session):
    from tests import template_lookups

    template_lookups.instalar()


def pytest_sessionfinish(session, exitstatus):
    """Fails the run on a template variable that is not found and was not before (decision 159)."""
    from tests import template_lookups

    relatorio = session.config.pluginmanager.get_plugin("terminalreporter")
    escrever = relatorio.write_line if relatorio else print
    if template_lookups.conferir(escrever) and exitstatus == 0:
        session.exitstatus = 1
