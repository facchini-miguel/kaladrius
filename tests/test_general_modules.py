"""General modules turned on and off by the clinic (decision 092), fictitious data only."""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.forms import ClinicForm
from apps.core.isolation import use_clinic
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
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from tests.test_modules_migration import estado_do_banco

pytestmark = pytest.mark.django_db

M = ModuleCode


def sem(*desligados):
    return GENERAL_MODULES - set(desligados)


@pytest.fixture
def patient(clinica_a):
    with use_clinic(clinica_a):
        return Patient.objects.create(name="Paciente fictício dos módulos")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_gerais", clinica_a, Role.ADMIN))


def test_clinica_nova_comeca_com_todos_os_modulos_gerais(clinica_a):
    with use_clinic(clinica_a):
        ligados = set(ClinicModule.objects.filter(active=True).values_list("code", flat=True))
    assert ligados == GENERAL_MODULES | {M.DENTISTRY}
    assert SPECIALTIES.isdisjoint(GENERAL_MODULES)


@pytest.mark.parametrize(
    ("modulo", "rota", "texto_do_menu"),
    [
        (M.SCHEDULE, "schedule:calendar", 'href="/schedule/"'),
        (M.RECALLS, "recalls:list", 'href="/recalls/"'),
        (M.BIRTHDAYS, "patients:birthdays", "/birthdays/"),
        (M.FINANCE, "finance:receivables", "/finance/"),
    ],
)
def test_modulo_desligado_some_do_menu_e_a_url_e_recusada(
    modulo, rota, texto_do_menu, clinica_a, admin, django_user_model, cliente_de
):
    desligados = {modulo, M.ESTIMATES, M.STAFF} if modulo == M.FINANCE else {modulo}
    assert texto_do_menu in admin.get(reverse("home")).content.decode()
    configure(clinica_a, sem(*desligados))
    assert texto_do_menu not in admin.get(reverse("home")).content.decode()
    assert admin.get(reverse(rota)).status_code == 403
    # The system administrator still reaches it, marked as off (decision 115).
    root = cliente_de(django_user_model.objects.create_superuser("root_gerais"))
    page = root.get(reverse(rota))
    assert page.status_code == 200
    assert "está desligado nesta clínica" in page.content.decode()
    menu = root.get(reverse("home")).content.decode()
    assert texto_do_menu in menu and ">desligado</span>" in menu


def test_orcamentos_desligado(clinica_a, admin, patient):
    configure(clinica_a, sem(M.ESTIMATES))
    assert admin.get(reverse("estimates:list")).status_code == 403
    ficha = admin.get(reverse("patients:record", args=[patient.pk]))
    assert ficha.context.get("orcamentos") is None
    assert "Novo orçamento" not in ficha.content.decode()


def test_prontuario_desligado_bloqueia_profissional_e_o_superusuario_ve_marcado(
    clinica_a, patient, criar_usuario, django_user_model, cliente_de
):
    user = criar_usuario("prof_gerais", clinica_a, Role.PRACTITIONER)
    with use_clinic(clinica_a):
        Practitioner.objects.create(name="Profissional fictício", user=user)
    url = reverse("medical_records:new", args=[patient.pk])
    cliente = cliente_de(user)
    assert cliente.get(url).status_code == 200
    configure(clinica_a, sem(M.MEDICAL_RECORDS))
    assert cliente.get(url).status_code == 403
    assert (
        "Novo atendimento"
        not in cliente.get(reverse("patients:record", args=[patient.pk])).content.decode()
    )
    root = cliente_de(django_user_model.objects.create_superuser("root_prontuario"))
    page = root.get(url)
    assert page.status_code == 200
    assert "O módulo Prontuário está desligado nesta clínica" in page.content.decode()


def test_desligar_nao_apaga_dados_e_religar_mostra_de_novo(clinica_a, admin, patient):
    with use_clinic(clinica_a):
        Recall.objects.create(
            patient=patient, date=datetime.date(2026, 11, 10), description="Retorno"
        )
    configure(clinica_a, sem(M.RECALLS))
    assert admin.get(reverse("recalls:list")).status_code == 403
    with use_clinic(clinica_a):
        assert Recall.objects.count() == 1
    configure(clinica_a, GENERAL_MODULES)
    assert "Retorno" in admin.get(reverse("recalls:list")).content.decode()


def test_so_o_nucleo_ligado_sem_resumo_vazio(clinica_a, admin):
    """Review stage 4: with every optional module off, "Resumo do dia" stood alone."""
    configure(clinica_a, set())
    page = admin.get(reverse("home")).content.decode()
    assert "Resumo do dia" not in page and "Novo paciente" in page


def test_orcamentos_precisa_do_financeiro(clinica_a):
    with pytest.raises(ValidationError):
        configure(clinica_a, sem(M.FINANCE))
    data = {
        "name": "Clínica fictícia",
        "area": "odontologia",
        "schedule_start": "08:00",
        "schedule_end": "18:00",
        "schedule_interval": 30,
        "modulos": ["odontologia"],
        "modulos_gerais": sorted(sem(M.FINANCE)),
    }
    form = ClinicForm(data, instance=clinica_a)
    assert not form.is_valid()
    assert "modulos_gerais" in form.errors
    data["modulos_gerais"] = sorted(sem(M.FINANCE, M.ESTIMATES, M.STAFF))
    assert ClinicForm(data, instance=clinica_a).is_valid()


def test_configuracoes_salvam_os_modulos_gerais(clinica_a, admin):
    response = admin.post(
        reverse("clinic_settings"),
        {
            "name": "Clínica fictícia",
            "area": "medicina",
            "schedule_start": "08:00",
            "schedule_end": "18:00",
            "schedule_interval": 30,
            "modulos": ["medicina"],
            "modulos_gerais": [M.SCHEDULE, M.MEDICAL_RECORDS],
        },
    )
    assert response.status_code == 302
    with use_clinic(clinica_a):
        ligados = set(ClinicModule.objects.filter(active=True).values_list("code", flat=True))
    assert ligados == {M.MEDICINE, M.SCHEDULE, M.MEDICAL_RECORDS}
    page = admin.get(reverse("clinic_settings")).content.decode()
    assert "Especialidades" in page and "Módulos" in page


def test_cadastro_da_primeira_clinica_liga_todos_os_modulos_gerais(django_user_model, cliente_de):
    cliente = cliente_de(django_user_model.objects.create_superuser("root_primeira"))
    response = cliente.post(
        reverse("register_clinic"),
        {"name": "Clínica fictícia", "area": "medicina", "modulos": ["medicina"]},
    )
    assert response.status_code == 302
    clinic = Clinic.objects.get()
    with use_clinic(clinic):
        ligados = set(ClinicModule.objects.filter(active=True).values_list("code", flat=True))
    assert ligados == GENERAL_MODULES | {M.MEDICINE}


def test_permissoes_leem_os_modulos_uma_vez_por_requisicao(admin):
    with CaptureQueriesContext(connection) as consultas:
        assert admin.get(reverse("home")).status_code == 200
    modulos = [q for q in consultas if 'FROM "core_modulodaclinica"' in q["sql"]]
    assert len(modulos) == 1


@pytest.mark.django_db(transaction=True)
def test_migracao_liga_os_modulos_gerais_das_clinicas_existentes():
    executor = MigrationExecutor(connection)
    folhas = executor.loader.graph.leaf_nodes()
    previous = [("core", "0010_modulos_clinicos")]
    try:
        executor.migrate(previous)
        apps = estado_do_banco()
        Antiga = apps.get_model("core", "Clinica")
        ModuloAntigo = apps.get_model("core", "ModuloDaClinica")
        clinic = Antiga.objects.create(nome="Clínica fictícia antiga", area="medicina")
        ModuloAntigo.objects.bulk_create(
            [
                ModuloAntigo(clinica_id=clinic.pk, codigo="odontologia", ativo=False),
                ModuloAntigo(clinica_id=clinic.pk, codigo="medicina", ativo=True),
            ]
        )
        executor = MigrationExecutor(connection)
        executor.migrate([("core", "0011_modulos_gerais")])
        Module = executor.loader.project_state([("core", "0011_modulos_gerais")]).apps.get_model(
            "core", "ModuloDaClinica"
        )
        ligados = set(
            Module.objects.filter(clinica_id=clinic.pk, ativo=True).values_list("codigo", flat=True)
        )
        # Pessoal came later (core 0012), so it is not part of this step.
        assert ligados == {"medicina", *GENERAL_MODULES} - {"pessoal"}
        assert Module.objects.filter(clinica_id=clinic.pk).count() == len(ModuleCode) - 1
    finally:
        MigrationExecutor(connection).migrate(folhas)


def test_whatsapp_no_cadastro_e_na_ficha(clinica_a, admin):
    response = admin.post(
        reverse("patients:new"),
        {"kind": "PF", "name": "Paciente fictícia do WhatsApp", "whatsapp": "(48) 99999-0000"},
    )
    assert response.status_code == 302, response.context["form"].errors
    with use_clinic(clinica_a):
        patient = Patient.objects.get(name="Paciente fictícia do WhatsApp")
    assert patient.whatsapp == "48999990000"
    ficha = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert 'href="https://wa.me/5548999990000"' in ficha
    assert whatsapp("123") == "" and whatsapp("") == ""


def test_modulo_ligado_nao_mostra_aviso_ao_superusuario(clinica_a, django_user_model, cliente_de):
    root = cliente_de(django_user_model.objects.create_superuser("root_ligado"))
    for page in (reverse("home"), reverse("schedule:calendar")):
        content = root.get(page).content.decode()
        assert "está desligado nesta clínica" not in content
        assert ">desligado</span>" not in content
