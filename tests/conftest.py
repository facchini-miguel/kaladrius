import pytest

from apps.core.isolation import use_clinic
from apps.core.models import Clinic, Membership, Role
from apps.practitioners.models import Practitioner

PASSWORD = "senha-de-teste-123"


@pytest.fixture
def clinic_a(db):
    return Clinic.objects.create(name="Clínica A")


@pytest.fixture
def clinic_b(db):
    return Clinic.objects.create(name="Clínica B")


@pytest.fixture
def create_user(django_user_model):
    """Create a user, optionally linked to a clinic with a role."""

    def create(username, clinic=None, role=Role.FRONT_DESK, **extra):
        user = django_user_model.objects.create_user(username=username, password=PASSWORD, **extra)
        if clinic is not None:
            Membership.objects.create(user=user, clinic=clinic, role=role)
        return user

    return create


@pytest.fixture
def create_practitioner():
    """Create a practitioner inside the given clinic."""

    def create(clinic, name, **extra):
        with use_clinic(clinic):
            return Practitioner.objects.create(name=name, **extra)

    return create


@pytest.fixture
def client_for(client):
    """Log the test client in as the given user."""

    def log_in(user):
        client.force_login(user)
        return client

    return log_in


def pytest_sessionstart(session):
    from tests import template_lookups

    template_lookups.install()


def pytest_sessionfinish(session, exitstatus):
    """Fails the run on a template variable that is not found and was not before (decision 159)."""
    from tests import template_lookups

    report = session.config.pluginmanager.get_plugin("terminalreporter")
    write = report.write_line if report else print
    if template_lookups.check(write) and exitstatus == 0:
        session.exitstatus = 1
