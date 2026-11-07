"""General modules turned on and off by the clinic (decision 092), fictitious data only."""

import datetime
import importlib

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.forms import ClinicForm
from apps.core.isolation import use_clinic, without_isolation
from apps.core.models import (
    GENERAL_MODULES,
    SPECIALTIES,
    Clinic,
    ClinicModule,
    ModuleCode,
    Role,
)
from apps.core.modules import configure
from apps.core.templatetags.formats import whatsapp
from apps.core.values import VALUES
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from tests.era import apps_at, tables_of_the_time

pytestmark = pytest.mark.django_db

M = ModuleCode


def without(*turned_off):
    return GENERAL_MODULES - set(turned_off)


@pytest.fixture
def patient(clinic_a):
    with use_clinic(clinic_a):
        return Patient.objects.create(name="Paciente fictício dos módulos")


@pytest.fixture
def admin(clinic_a, create_user, client_for):
    return client_for(create_user("admin_gerais", clinic_a, Role.ADMIN))


def test_new_clinic_starts_with_all_general_modules(clinic_a):
    with use_clinic(clinic_a):
        turned_on = set(ClinicModule.objects.filter(active=True).values_list("code", flat=True))
    assert turned_on == GENERAL_MODULES | {M.DENTISTRY}
    assert SPECIALTIES.isdisjoint(GENERAL_MODULES)


@pytest.mark.parametrize(
    ("module", "route", "menu_text"),
    [
        (M.SCHEDULE, "schedule:calendar", 'href="/schedule/"'),
        (M.RECALLS, "recalls:list", 'href="/recalls/"'),
        (M.BIRTHDAYS, "patients:birthdays", "/birthdays/"),
        (M.FINANCE, "finance:receivables", "/finance/"),
    ],
)
def test_module_off_hides_menu_and_refuses_url(
    module, route, menu_text, clinic_a, admin, django_user_model, client_for
):
    turned_off = {module, M.ESTIMATES, M.STAFF} if module == M.FINANCE else {module}
    assert menu_text in admin.get(reverse("home")).content.decode()
    configure(clinic_a, without(*turned_off))
    assert menu_text not in admin.get(reverse("home")).content.decode()
    assert admin.get(reverse(route)).status_code == 403
    # The system administrator still reaches it, marked as off (decision 115).
    root = client_for(django_user_model.objects.create_superuser("root_gerais"))
    page = root.get(reverse(route))
    assert page.status_code == 200
    assert "está desligado nesta clínica" in page.content.decode()
    menu = root.get(reverse("home")).content.decode()
    assert menu_text in menu and ">desligado</span>" in menu


def test_estimates_off(clinic_a, admin, patient):
    configure(clinic_a, without(M.ESTIMATES))
    assert admin.get(reverse("estimates:list")).status_code == 403
    patient_record = admin.get(reverse("patients:record", args=[patient.pk]))
    assert patient_record.context.get("estimates") is None
    assert "Novo orçamento" not in patient_record.content.decode()


def test_records_off_blocks_practitioner_and_superuser_sees_it_marked(
    clinic_a, patient, create_user, django_user_model, client_for
):
    user = create_user("prof_gerais", clinic_a, Role.PRACTITIONER)
    with use_clinic(clinic_a):
        Practitioner.objects.create(name="Profissional fictício", user=user)
    url = reverse("medical_records:new", args=[patient.pk])
    user_client = client_for(user)
    assert user_client.get(url).status_code == 200
    configure(clinic_a, without(M.MEDICAL_RECORDS))
    assert user_client.get(url).status_code == 403
    assert (
        "Novo atendimento"
        not in user_client.get(reverse("patients:record", args=[patient.pk])).content.decode()
    )
    root = client_for(django_user_model.objects.create_superuser("root_prontuario"))
    page = root.get(url)
    assert page.status_code == 200
    assert "O módulo Prontuário está desligado nesta clínica" in page.content.decode()


def test_turning_off_keeps_data_and_turning_on_shows_again(clinic_a, admin, patient):
    with use_clinic(clinic_a):
        Recall.objects.create(
            patient=patient, date=datetime.date(2026, 11, 10), description="Retorno"
        )
    configure(clinic_a, without(M.RECALLS))
    assert admin.get(reverse("recalls:list")).status_code == 403
    with use_clinic(clinic_a):
        assert Recall.objects.count() == 1
    configure(clinic_a, GENERAL_MODULES)
    assert "Retorno" in admin.get(reverse("recalls:list")).content.decode()


def test_only_core_on_without_empty_summary(clinic_a, admin):
    """Review stage 4: with every optional module off, "Resumo do dia" stood alone."""
    configure(clinic_a, set())
    page = admin.get(reverse("home")).content.decode()
    assert "Resumo do dia" not in page and "Novo paciente" in page


def test_estimates_needs_finance(clinic_a):
    with pytest.raises(ValidationError):
        configure(clinic_a, without(M.FINANCE))
    data = {
        "name": "Clínica fictícia",
        "area": "dentistry",
        "schedule_start": "08:00",
        "schedule_end": "18:00",
        "schedule_interval": 30,
        "modules": ["dentistry"],
        "general_modules": sorted(without(M.FINANCE)),
    }
    form = ClinicForm(data, instance=clinic_a)
    assert not form.is_valid()
    assert "general_modules" in form.errors
    data["general_modules"] = sorted(without(M.FINANCE, M.ESTIMATES, M.STAFF))
    assert ClinicForm(data, instance=clinic_a).is_valid()


def test_settings_save_the_general_modules(clinic_a, admin):
    response = admin.post(
        reverse("clinic_settings"),
        {
            "name": "Clínica fictícia",
            "area": "medicine",
            "schedule_start": "08:00",
            "schedule_end": "18:00",
            "schedule_interval": 30,
            "modules": ["medicine"],
            "general_modules": [M.SCHEDULE, M.MEDICAL_RECORDS],
        },
    )
    assert response.status_code == 302
    with use_clinic(clinic_a):
        turned_on = set(ClinicModule.objects.filter(active=True).values_list("code", flat=True))
    assert turned_on == {M.MEDICINE, M.SCHEDULE, M.MEDICAL_RECORDS}
    page = admin.get(reverse("clinic_settings")).content.decode()
    assert "Especialidades" in page and "Módulos" in page


def test_first_clinic_registration_turns_on_all_general_modules(django_user_model, client_for):
    user_client = client_for(django_user_model.objects.create_superuser("root_primeira"))
    response = user_client.post(
        reverse("register_clinic"),
        {"name": "Clínica fictícia", "area": "medicine", "modules": ["medicine"]},
    )
    assert response.status_code == 302
    clinic = Clinic.objects.get()
    with use_clinic(clinic):
        turned_on = set(ClinicModule.objects.filter(active=True).values_list("code", flat=True))
    assert turned_on == GENERAL_MODULES | {M.MEDICINE}


def test_permissions_read_modules_once_per_request(admin):
    with CaptureQueriesContext(connection) as queries:
        assert admin.get(reverse("home")).status_code == 200
    modules = [q for q in queries if 'FROM "core_clinic_module"' in q["sql"]]
    assert len(modules) == 1


def test_migration_turns_on_general_modules_of_existing_clinics():
    """Migration core 0011 turned on the general modules of the clinics that existed."""
    clinic = Clinic.objects.create(name="Clínica fictícia antiga", area="medicina")
    with without_isolation():
        # As the clinic was after 0010: only the clinical modules.
        ClinicModule.all_objects.filter(clinic=clinic).delete()
        ClinicModule.all_objects.bulk_create(
            [
                ClinicModule(clinic=clinic, code="odontologia", active=False),
                ClinicModule(clinic=clinic, code="medicina", active=True),
            ]
        )
    apps = apps_at(("core", "0011_modulos_gerais"))
    pairs_ = [
        (apps.get_model("core", "Clinica"), Clinic),
        (apps.get_model("core", "ModuloDaClinica"), ClinicModule),
    ]
    with tables_of_the_time(pairs_), connection.schema_editor() as editor:
        importlib.import_module("apps.core.migrations.0011_modulos_gerais").ligar_modulos_gerais(
            apps, editor
        )
    with without_isolation():
        turned_on = set(
            ClinicModule.objects.filter(clinic=clinic, active=True).values_list("code", flat=True)
        )
        # Pessoal came later (core 0012), so it is not part of this step.
        # The migration wrote the codes of its time (decision 198).
        codes = VALUES["core.ClinicModule.code"]
        assert {codes.get(c, c) for c in turned_on} == {"medicine", *GENERAL_MODULES} - {"staff"}
        assert ClinicModule.objects.filter(clinic=clinic).count() == len(ModuleCode) - 1


def test_whatsapp_in_registration_and_record(clinic_a, admin):
    response = admin.post(
        reverse("patients:new"),
        {
            "kind": "individual",
            "name": "Paciente fictícia do WhatsApp",
            "whatsapp": "(48) 99999-0000",
        },
    )
    assert response.status_code == 302, response.context["form"].errors
    with use_clinic(clinic_a):
        patient = Patient.objects.get(name="Paciente fictícia do WhatsApp")
    assert patient.whatsapp == "48999990000"
    patient_record = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert 'href="https://wa.me/5548999990000"' in patient_record
    assert whatsapp("123") == "" and whatsapp("") == ""


def test_module_on_shows_no_warning_to_superuser(clinic_a, django_user_model, client_for):
    root = client_for(django_user_model.objects.create_superuser("root_ligado"))
    for page in (reverse("home"), reverse("schedule:calendar")):
        content = root.get(page).content.decode()
        assert "está desligado nesta clínica" not in content
        assert ">desligado</span>" not in content
