"""General modules turned on and off by the clinic (decision 092), fictitious data only."""

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.core.forms import ClinicaForm
from apps.core.isolamento import usar_clinica
from apps.core.models import (
    ESPECIALIDADES,
    MODULOS_GERAIS,
    Clinica,
    ModuloClinico,
    ModuloDaClinica,
    Papel,
)
from apps.core.modulos import configurar
from apps.core.templatetags.formatos import whatsapp
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada

pytestmark = pytest.mark.django_db

M = ModuloClinico


def sem(*desligados):
    return MODULOS_GERAIS - set(desligados)


@pytest.fixture
def paciente(clinica_a):
    with usar_clinica(clinica_a):
        return Paciente.objects.create(nome="Paciente fictício dos módulos")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_gerais", clinica_a, Papel.ADMIN))


def test_clinica_nova_comeca_com_todos_os_modulos_gerais(clinica_a):
    with usar_clinica(clinica_a):
        ligados = set(ModuloDaClinica.objects.filter(ativo=True).values_list("codigo", flat=True))
    assert ligados == MODULOS_GERAIS | {M.ODONTOLOGIA}
    assert ESPECIALIDADES.isdisjoint(MODULOS_GERAIS)


@pytest.mark.parametrize(
    ("modulo", "rota", "texto_do_menu"),
    [
        (M.AGENDA, "agenda:calendario", 'href="/agenda/"'),
        (M.RECHAMADAS, "rechamadas:lista", 'href="/rechamadas/"'),
        (M.ANIVERSARIANTES, "pacientes:aniversariantes", "/aniversariantes/"),
        (M.FINANCEIRO, "financeiro:receber", "/financeiro/"),
    ],
)
def test_modulo_desligado_some_do_menu_e_a_url_e_recusada(
    modulo, rota, texto_do_menu, clinica_a, admin, django_user_model, cliente_de
):
    desligados = {modulo, M.ORCAMENTOS, M.PESSOAL} if modulo == M.FINANCEIRO else {modulo}
    assert texto_do_menu in admin.get(reverse("inicio")).content.decode()
    configurar(clinica_a, sem(*desligados))
    assert texto_do_menu not in admin.get(reverse("inicio")).content.decode()
    assert admin.get(reverse(rota)).status_code == 403
    # Not even the system administrator reaches a module the clinic turned off.
    root = cliente_de(django_user_model.objects.create_superuser("root_gerais"))
    assert root.get(reverse(rota)).status_code == 403


def test_orcamentos_desligado(clinica_a, admin, paciente):
    configurar(clinica_a, sem(M.ORCAMENTOS))
    assert admin.get(reverse("orcamentos:lista")).status_code == 403
    ficha = admin.get(reverse("pacientes:ficha", args=[paciente.pk]))
    assert ficha.context.get("orcamentos") is None
    assert "Novo orçamento" not in ficha.content.decode()


def test_prontuario_desligado_bloqueia_profissional_e_superusuario(
    clinica_a, paciente, criar_usuario, django_user_model, cliente_de
):
    usuario = criar_usuario("prof_gerais", clinica_a, Papel.PROFISSIONAL)
    with usar_clinica(clinica_a):
        Profissional.objects.create(nome="Profissional fictício", usuario=usuario)
    url = reverse("prontuario:novo", args=[paciente.pk])
    cliente = cliente_de(usuario)
    assert cliente.get(url).status_code == 200
    configurar(clinica_a, sem(M.PRONTUARIO))
    assert cliente.get(url).status_code == 403
    assert (
        "Novo atendimento"
        not in cliente.get(reverse("pacientes:ficha", args=[paciente.pk])).content.decode()
    )
    root = cliente_de(django_user_model.objects.create_superuser("root_prontuario"))
    assert root.get(url).status_code == 403


def test_desligar_nao_apaga_dados_e_religar_mostra_de_novo(clinica_a, admin, paciente):
    with usar_clinica(clinica_a):
        Rechamada.objects.create(
            paciente=paciente, data=datetime.date(2026, 11, 10), descricao="Retorno"
        )
    configurar(clinica_a, sem(M.RECHAMADAS))
    assert admin.get(reverse("rechamadas:lista")).status_code == 403
    with usar_clinica(clinica_a):
        assert Rechamada.objects.count() == 1
    configurar(clinica_a, MODULOS_GERAIS)
    assert "Retorno" in admin.get(reverse("rechamadas:lista")).content.decode()


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
        reverse("configuracoes"),
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
        ligados = set(ModuloDaClinica.objects.filter(ativo=True).values_list("codigo", flat=True))
    assert ligados == {M.MEDICINA, M.AGENDA, M.PRONTUARIO}
    pagina = admin.get(reverse("configuracoes")).content.decode()
    assert "Especialidades" in pagina and "Módulos" in pagina


def test_cadastro_da_primeira_clinica_liga_todos_os_modulos_gerais(django_user_model, cliente_de):
    cliente = cliente_de(django_user_model.objects.create_superuser("root_primeira"))
    resposta = cliente.post(
        reverse("cadastrar_clinica"),
        {"nome": "Clínica fictícia", "area": "medicina", "modulos": ["medicina"]},
    )
    assert resposta.status_code == 302
    clinica = Clinica.objects.get()
    with usar_clinica(clinica):
        ligados = set(ModuloDaClinica.objects.filter(ativo=True).values_list("codigo", flat=True))
    assert ligados == MODULOS_GERAIS | {M.MEDICINA}


def test_permissoes_leem_os_modulos_uma_vez_por_requisicao(admin):
    with CaptureQueriesContext(connection) as consultas:
        assert admin.get(reverse("inicio")).status_code == 200
    modulos = [q for q in consultas if 'FROM "core_modulodaclinica"' in q["sql"]]
    assert len(modulos) == 1


@pytest.mark.django_db(transaction=True)
def test_migracao_liga_os_modulos_gerais_das_clinicas_existentes():
    executor = MigrationExecutor(connection)
    folhas = executor.loader.graph.leaf_nodes()
    anterior = [("core", "0010_modulos_clinicos")]
    try:
        executor.migrate(anterior)
        estado = [folha for folha in folhas if folha[0] != "core"] + anterior
        apps = executor.loader.project_state(estado).apps
        Antiga = apps.get_model("core", "Clinica")
        ModuloAntigo = apps.get_model("core", "ModuloDaClinica")
        clinica = Antiga.objects.create(nome="Clínica fictícia antiga", area="medicina")
        ModuloAntigo.objects.bulk_create(
            [
                ModuloAntigo(clinica_id=clinica.pk, codigo="odontologia", ativo=False),
                ModuloAntigo(clinica_id=clinica.pk, codigo="medicina", ativo=True),
            ]
        )
        executor = MigrationExecutor(connection)
        executor.migrate([("core", "0011_modulos_gerais")])
        Modulo = executor.loader.project_state([("core", "0011_modulos_gerais")]).apps.get_model(
            "core", "ModuloDaClinica"
        )
        ligados = set(
            Modulo.objects.filter(clinica_id=clinica.pk, ativo=True).values_list(
                "codigo", flat=True
            )
        )
        # Pessoal came later (core 0012), so it is not part of this step.
        assert ligados == {"medicina", *MODULOS_GERAIS} - {"pessoal"}
        assert Modulo.objects.filter(clinica_id=clinica.pk).count() == len(ModuloClinico) - 1
    finally:
        MigrationExecutor(connection).migrate(folhas)


def test_whatsapp_no_cadastro_e_na_ficha(clinica_a, admin):
    resposta = admin.post(
        reverse("pacientes:novo"),
        {"tipo": "PF", "nome": "Paciente fictícia do WhatsApp", "whatsapp": "(48) 99999-0000"},
    )
    assert resposta.status_code == 302, resposta.context["form"].errors
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.get(nome="Paciente fictícia do WhatsApp")
    assert paciente.whatsapp == "48999990000"
    ficha = admin.get(reverse("pacientes:ficha", args=[paciente.pk])).content.decode()
    assert 'href="https://wa.me/5548999990000"' in ficha
    assert whatsapp("123") == "" and whatsapp("") == ""
