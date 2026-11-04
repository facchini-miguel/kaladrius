"""General modules turned on and off by the clinic (decision 092), fictitious data only."""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.forms import ClinicaForm
from apps.core.isolation import usar_clinica
from apps.core.models import (
    ESPECIALIDADES,
    MODULOS_GERAIS,
    Clinic,
    ClinicModule,
    ModuloClinico,
    Papel,
)
from apps.core.modules import configurar
from apps.core.templatetags.formats import whatsapp
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from tests.test_modules_migration import estado_do_banco

pytestmark = pytest.mark.django_db

M = ModuloClinico


def sem(*desligados):
    return MODULOS_GERAIS - set(desligados)


@pytest.fixture
def paciente(clinica_a):
    with usar_clinica(clinica_a):
        return Patient.objects.create(nome="Paciente fictício dos módulos")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_gerais", clinica_a, Papel.ADMIN))


def test_clinica_nova_comeca_com_todos_os_modulos_gerais(clinica_a):
    with usar_clinica(clinica_a):
        ligados = set(ClinicModule.objects.filter(ativo=True).values_list("codigo", flat=True))
    assert ligados == MODULOS_GERAIS | {M.ODONTOLOGIA}
    assert ESPECIALIDADES.isdisjoint(MODULOS_GERAIS)


@pytest.mark.parametrize(
    ("modulo", "rota", "texto_do_menu"),
    [
        (M.AGENDA, "schedule:calendar", 'href="/schedule/"'),
        (M.RECHAMADAS, "recalls:list", 'href="/recalls/"'),
        (M.ANIVERSARIANTES, "patients:birthdays", "/birthdays/"),
        (M.FINANCEIRO, "finance:receivables", "/finance/"),
    ],
)
def test_modulo_desligado_some_do_menu_e_a_url_e_recusada(
    modulo, rota, texto_do_menu, clinica_a, admin, django_user_model, cliente_de
):
    desligados = {modulo, M.ORCAMENTOS, M.PESSOAL} if modulo == M.FINANCEIRO else {modulo}
    assert texto_do_menu in admin.get(reverse("home")).content.decode()
    configurar(clinica_a, sem(*desligados))
    assert texto_do_menu not in admin.get(reverse("home")).content.decode()
    assert admin.get(reverse(rota)).status_code == 403
    # The system administrator still reaches it, marked as off (decision 115).
    root = cliente_de(django_user_model.objects.create_superuser("root_gerais"))
    pagina = root.get(reverse(rota))
    assert pagina.status_code == 200
    assert "está desligado nesta clínica" in pagina.content.decode()
    menu = root.get(reverse("home")).content.decode()
    assert texto_do_menu in menu and ">desligado</span>" in menu


def test_orcamentos_desligado(clinica_a, admin, paciente):
    configurar(clinica_a, sem(M.ORCAMENTOS))
    assert admin.get(reverse("estimates:list")).status_code == 403
    ficha = admin.get(reverse("patients:record", args=[paciente.pk]))
    assert ficha.context.get("orcamentos") is None
    assert "Novo orçamento" not in ficha.content.decode()


def test_prontuario_desligado_bloqueia_profissional_e_o_superusuario_ve_marcado(
    clinica_a, paciente, criar_usuario, django_user_model, cliente_de
):
    usuario = criar_usuario("prof_gerais", clinica_a, Papel.PROFISSIONAL)
    with usar_clinica(clinica_a):
        Practitioner.objects.create(nome="Profissional fictício", usuario=usuario)
    url = reverse("medical_records:new", args=[paciente.pk])
    cliente = cliente_de(usuario)
    assert cliente.get(url).status_code == 200
    configurar(clinica_a, sem(M.PRONTUARIO))
    assert cliente.get(url).status_code == 403
    assert (
        "Novo atendimento"
        not in cliente.get(reverse("patients:record", args=[paciente.pk])).content.decode()
    )
    root = cliente_de(django_user_model.objects.create_superuser("root_prontuario"))
    pagina = root.get(url)
    assert pagina.status_code == 200
    assert "O módulo Prontuário está desligado nesta clínica" in pagina.content.decode()


def test_desligar_nao_apaga_dados_e_religar_mostra_de_novo(clinica_a, admin, paciente):
    with usar_clinica(clinica_a):
        Recall.objects.create(
            paciente=paciente, data=datetime.date(2026, 11, 10), descricao="Retorno"
        )
    configurar(clinica_a, sem(M.RECHAMADAS))
    assert admin.get(reverse("recalls:list")).status_code == 403
    with usar_clinica(clinica_a):
        assert Recall.objects.count() == 1
    configurar(clinica_a, MODULOS_GERAIS)
    assert "Retorno" in admin.get(reverse("recalls:list")).content.decode()


def test_so_o_nucleo_ligado_sem_resumo_vazio(clinica_a, admin):
    """Review stage 4: with every optional module off, "Resumo do dia" stood alone."""
    configurar(clinica_a, set())
    pagina = admin.get(reverse("home")).content.decode()
    assert "Resumo do dia" not in pagina and "Novo paciente" in pagina


def test_orcamentos_precisa_do_financeiro(clinica_a):
    with pytest.raises(ValidationError):
        configurar(clinica_a, sem(M.FINANCEIRO))
    dados = {
        "nome": "Clínica fictícia",
        "area": "odontologia",
        "agenda_inicio": "08:00",
        "agenda_fim": "18:00",
        "agenda_intervalo": 30,
        "modulos": ["odontologia"],
        "modulos_gerais": sorted(sem(M.FINANCEIRO)),
    }
    form = ClinicaForm(dados, instance=clinica_a)
    assert not form.is_valid()
    assert "modulos_gerais" in form.errors
    dados["modulos_gerais"] = sorted(sem(M.FINANCEIRO, M.ORCAMENTOS, M.PESSOAL))
    assert ClinicaForm(dados, instance=clinica_a).is_valid()


def test_configuracoes_salvam_os_modulos_gerais(clinica_a, admin):
    resposta = admin.post(
        reverse("clinic_settings"),
        {
            "nome": "Clínica fictícia",
            "area": "medicina",
            "agenda_inicio": "08:00",
            "agenda_fim": "18:00",
            "agenda_intervalo": 30,
            "modulos": ["medicina"],
            "modulos_gerais": [M.AGENDA, M.PRONTUARIO],
        },
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        ligados = set(ClinicModule.objects.filter(ativo=True).values_list("codigo", flat=True))
    assert ligados == {M.MEDICINA, M.AGENDA, M.PRONTUARIO}
    pagina = admin.get(reverse("clinic_settings")).content.decode()
    assert "Especialidades" in pagina and "Módulos" in pagina


def test_cadastro_da_primeira_clinica_liga_todos_os_modulos_gerais(django_user_model, cliente_de):
    cliente = cliente_de(django_user_model.objects.create_superuser("root_primeira"))
    resposta = cliente.post(
        reverse("register_clinic"),
        {"nome": "Clínica fictícia", "area": "medicina", "modulos": ["medicina"]},
    )
    assert resposta.status_code == 302
    clinic = Clinic.objects.get()
    with usar_clinica(clinic):
        ligados = set(ClinicModule.objects.filter(ativo=True).values_list("codigo", flat=True))
    assert ligados == MODULOS_GERAIS | {M.MEDICINA}


def test_permissoes_leem_os_modulos_uma_vez_por_requisicao(admin):
    with CaptureQueriesContext(connection) as consultas:
        assert admin.get(reverse("home")).status_code == 200
    modulos = [q for q in consultas if 'FROM "core_modulodaclinica"' in q["sql"]]
    assert len(modulos) == 1


@pytest.mark.django_db(transaction=True)
def test_migracao_liga_os_modulos_gerais_das_clinicas_existentes():
    executor = MigrationExecutor(connection)
    folhas = executor.loader.graph.leaf_nodes()
    anterior = [("core", "0010_modulos_clinicos")]
    try:
        executor.migrate(anterior)
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
        Modulo = executor.loader.project_state([("core", "0011_modulos_gerais")]).apps.get_model(
            "core", "ModuloDaClinica"
        )
        ligados = set(
            Modulo.objects.filter(clinica_id=clinic.pk, ativo=True).values_list("codigo", flat=True)
        )
        # Pessoal came later (core 0012), so it is not part of this step.
        assert ligados == {"medicina", *MODULOS_GERAIS} - {"pessoal"}
        assert Modulo.objects.filter(clinica_id=clinic.pk).count() == len(ModuloClinico) - 1
    finally:
        MigrationExecutor(connection).migrate(folhas)


def test_whatsapp_no_cadastro_e_na_ficha(clinica_a, admin):
    resposta = admin.post(
        reverse("patients:new"),
        {"tipo": "PF", "nome": "Paciente fictícia do WhatsApp", "whatsapp": "(48) 99999-0000"},
    )
    assert resposta.status_code == 302, resposta.context["form"].errors
    with usar_clinica(clinica_a):
        paciente = Patient.objects.get(nome="Paciente fictícia do WhatsApp")
    assert paciente.whatsapp == "48999990000"
    ficha = admin.get(reverse("patients:record", args=[paciente.pk])).content.decode()
    assert 'href="https://wa.me/5548999990000"' in ficha
    assert whatsapp("123") == "" and whatsapp("") == ""


def test_modulo_ligado_nao_mostra_aviso_ao_superusuario(clinica_a, django_user_model, cliente_de):
    root = cliente_de(django_user_model.objects.create_superuser("root_ligado"))
    for pagina in (reverse("home"), reverse("schedule:calendar")):
        conteudo = root.get(pagina).content.decode()
        assert "está desligado nesta clínica" not in conteudo
        assert ">desligado</span>" not in conteudo
