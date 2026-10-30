"""Specialties are configured independently, using fictitious patients only."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.agenda.models import Agendamento, TipoAtendimento
from apps.auditoria.models import RegistroAuditoria
from apps.core.forms import ClinicaAdminForm, ClinicaForm
from apps.core.isolamento import ClinicaDiferente, SemClinicaAtual, usar_clinica
from apps.core.models import Clinica, ModuloDaClinica, Papel
from apps.core.modulos import configurar
from apps.orcamentos.models import ItemOrcamento, Orcamento
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

pytestmark = pytest.mark.django_db


def configuracao(**extra):
    return {
        "nome": "Clínica fictícia",
        "area": "medicina",
        "agenda_inicio": "07:30",
        "agenda_fim": "20:00",
        "agenda_intervalo": 30,
        "modulos": ["odontologia", "medicina"],
        **extra,
    }


@pytest.mark.parametrize("area", Clinica.Area.values)
def test_criacao_preserva_a_capacidade_da_area_original(area):
    clinica = Clinica.objects.create(nome="Clínica fictícia", area=area)
    assert clinica.odontologia == (area == "odontologia")
    assert clinica.medicina == (area == "medicina")
    with usar_clinica(clinica):
        assert ModuloDaClinica.objects.count() == 2


@pytest.mark.parametrize(
    "codigos", [[], ["medicina"], ["odontologia"], ["odontologia", "medicina"]]
)
def test_admin_configura_areas_independentes(codigos, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_modulos", clinica_a, Papel.ADMIN))
    resposta = cliente.post(reverse("configuracoes"), configuracao(modulos=codigos))
    assert resposta.status_code == 302
    clinica_a.refresh_from_db()
    assert clinica_a.area == "medicina"  # primary area does not dictate enabled modules
    assert clinica_a.odontologia == ("odontologia" in codigos)
    assert clinica_a.medicina == ("medicina" in codigos)


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL, Papel.FINANCEIRO])
def test_outros_papeis_nao_alteram_modulos(papel, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario_modulos", clinica_a, papel))
    assert cliente.post(reverse("configuracoes"), configuracao()).status_code == 403
    assert clinica_a.odontologia and not clinica_a.medicina


def test_administrador_de_demo_nao_altera_modulos(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("demo_modulos", clinica_a, Papel.ADMIN, demonstracao=True))
    assert cliente.post(reverse("configuracoes"), configuracao()).status_code == 403
    assert not clinica_a.medicina


def test_modulo_desconhecido_nao_grava_nem_no_servico_nem_no_form(clinica_a):
    with pytest.raises(ValidationError):
        configurar(clinica_a, {"desconhecido"})
    form = ClinicaForm(configuracao(modulos=["desconhecido"]), instance=clinica_a)
    assert not form.is_valid() and "modulos" in form.errors
    assert clinica_a.odontologia and not clinica_a.modulo_habilitado("desconhecido")


def test_modulos_sao_isolados_e_a_consulta_sem_clinica_falha(clinica_a, clinica_b):
    configurar(clinica_b, {"medicina"})
    with usar_clinica(clinica_a):
        assert set(ModuloDaClinica.objects.values_list("clinica_id", flat=True)) == {clinica_a.pk}
    with pytest.raises(SemClinicaAtual):
        ModuloDaClinica.objects.count()
    assert clinica_a.odontologia and not clinica_b.odontologia


def test_reconfiguracao_idempotente_preserva_ids_e_registra_mudanca(clinica_a):
    antes = dict(ModuloDaClinica.todos.filter(clinica=clinica_a).values_list("codigo", "pk"))
    configurar(clinica_a, {"medicina"})
    depois = dict(ModuloDaClinica.todos.filter(clinica=clinica_a).values_list("codigo", "pk"))
    assert antes == depois
    alteracoes = RegistroAuditoria.objects.filter(
        clinica=clinica_a, modelo="Módulo da clínica", acao=RegistroAuditoria.Acao.ALTERAR
    )
    assert alteracoes.count() == 2
    configurar(clinica_a, {"medicina"})
    assert alteracoes.count() == 2


def test_campos_administrativos_e_commit_false_preservados(clinica_a):
    form = ClinicaAdminForm(configuracao(ativa="on"), instance=clinica_a)
    assert "ativa" in form.fields and "modulos" in form.fields
    assert form.is_valid(), form.errors
    clinica = form.save(commit=False)
    assert not clinica.medicina
    clinica.save()
    form.save_m2m()
    assert clinica.medicina and clinica.odontologia


def test_django_admin_salva_modulos_e_audita_o_superusuario(
    clinica_a, django_user_model, cliente_de
):
    usuario = django_user_model.objects.create_superuser("root_config_ficticio")
    cliente = cliente_de(usuario)
    url = reverse("admin:core_clinica_change", args=[clinica_a.pk])
    pagina = cliente.get(url)
    assert pagina.status_code == 200
    assert set(pagina.context["adminform"].form.initial["modulos"]) == {"odontologia"}
    prefixo = pagina.context["inline_admin_formsets"][0].formset.prefix
    resposta = cliente.post(
        url,
        configuracao(
            ativa="on",
            modulos=["medicina"],
            **{
                f"{prefixo}-TOTAL_FORMS": "0",
                f"{prefixo}-INITIAL_FORMS": "0",
                f"{prefixo}-MIN_NUM_FORMS": "0",
                f"{prefixo}-MAX_NUM_FORMS": "1000",
                "_save": "Salvar",
            },
        ),
    )
    assert resposta.status_code == 302
    assert clinica_a.medicina and not clinica_a.odontologia
    assert (
        RegistroAuditoria.objects.filter(
            clinica=clinica_a,
            usuario=usuario,
            modelo="Módulo da clínica",
            acao=RegistroAuditoria.Acao.ALTERAR,
        ).count()
        == 2
    )
    assert cliente.get(reverse("admin:core_clinica_add")).status_code == 403


def test_validacao_da_agenda_no_admin_considera_so_a_clinica_editada(
    clinica_a, clinica_b, criar_profissional, django_user_model, cliente_de
):
    profissional = criar_profissional(clinica_b, "Profissional fictício B")
    inicio = timezone.localtime(timezone.now() + datetime.timedelta(days=2)).replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    with usar_clinica(clinica_b):
        Agendamento.objects.create(
            profissional=profissional,
            tipo=TipoAtendimento.objects.first(),
            inicio=inicio,
            fim=inicio + datetime.timedelta(minutes=30),
        )
    cliente = cliente_de(django_user_model.objects.create_superuser("root_agenda_ficticio"))
    url = reverse("admin:core_clinica_change", args=[clinica_a.pk])
    form = cliente.get(url).context["adminform"].form
    form = type(form)(configuracao(ativa="on"), instance=clinica_a)
    assert form.is_valid(), form.errors
    outro = type(form)(configuracao(ativa="on"), instance=clinica_b)
    assert not outro.is_valid()
    assert "Ajuste os agendamentos futuros" in str(outro.non_field_errors())


@pytest.fixture
def orcamento(clinica_a):
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.create(nome="Paciente inteiramente fictício")
        return Orcamento.objects.create(paciente=paciente)


def novo_item(orcamento, **extra):
    return ItemOrcamento(
        orcamento=orcamento,
        descricao="Procedimento fictício",
        valor_unitario=Decimal("10"),
        **extra,
    )


def test_detalhe_nao_consulta_modulos_para_cada_item(
    clinica_a, orcamento, criar_usuario, cliente_de
):
    with usar_clinica(clinica_a):
        for _ in range(4):
            novo_item(orcamento, dentes="11").save()
    cliente = cliente_de(criar_usuario("recepcao_consultas", clinica_a, Papel.RECEPCAO))
    with CaptureQueriesContext(connection) as consultas:
        resposta = cliente.get(reverse("orcamentos:detalhe", args=[orcamento.pk]))
    assert resposta.status_code == 200
    assert resposta.context["odontologia_habilitada"]
    consultas_modulos = [q for q in consultas if 'FROM "core_modulodaclinica"' in q["sql"]]
    assert len(consultas_modulos) <= 2


def test_modelo_bloqueia_dentes_sem_depender_da_tela(clinica_a, orcamento):
    configurar(clinica_a, {"medicina"})
    with usar_clinica(clinica_a):
        with pytest.raises(ValidationError):
            novo_item(orcamento, dentes="11").save()
        novo_item(orcamento).save()  # general estimates remain available
        assert ItemOrcamento.objects.count() == 1


def test_historico_dental_permanece_legivel_e_nao_editavel(clinica_a, orcamento):
    with usar_clinica(clinica_a):
        item = novo_item(orcamento, dentes="11", faces="V")
        item.save()
    configurar(clinica_a, {"medicina"})
    with usar_clinica(clinica_a):
        assert ItemOrcamento.objects.get().dentes == "11"
        item.dentes = item.faces = ""
        with pytest.raises(ValidationError):
            item.save()
        with pytest.raises(ValidationError):
            item.delete()
    configurar(clinica_a, {"odontologia", "medicina"})
    with usar_clinica(clinica_a):
        item.refresh_from_db()
        item.delete()


def test_http_nao_remove_historico_quando_modulo_desativado(
    clinica_a, orcamento, criar_usuario, cliente_de
):
    with usar_clinica(clinica_a):
        item = novo_item(orcamento, faces="Arcada superior")
        item.save()
    configurar(clinica_a, {"medicina"})
    cliente = cliente_de(criar_usuario("recepcao_modulos", clinica_a, Papel.RECEPCAO))
    detalhe = cliente.get(reverse("orcamentos:detalhe", args=[orcamento.pk]))
    assert detalhe.status_code == 200 and detalhe.context["mostrar_dentes"]
    assert "Arcada superior" in detalhe.content.decode()
    assert (
        cliente.post(reverse("orcamentos:item_remover", args=[orcamento.pk, item.pk])).status_code
        == 403
    )
    with usar_clinica(clinica_a):
        assert ItemOrcamento.objects.filter(pk=item.pk).exists()


def test_item_nao_pode_vincular_orcamento_de_outra_clinica(clinica_b, orcamento):
    with usar_clinica(clinica_b), pytest.raises(ClinicaDiferente):
        novo_item(orcamento, dentes="11").save()


@pytest.mark.parametrize("codigos", [[], ["medicina"], ["odontologia", "medicina"]])
def test_prontuario_comum_nao_exige_modulo_especializado(
    codigos, clinica_a, orcamento, criar_usuario, cliente_de
):
    configurar(clinica_a, codigos)
    usuario = criar_usuario("prof_modulos", clinica_a, Papel.PROFISSIONAL)
    with usar_clinica(clinica_a):
        Profissional.objects.create(nome="Profissional fictício", usuario=usuario)
    cliente = cliente_de(usuario)
    assert cliente.get(reverse("prontuario:novo", args=[orcamento.paciente_id])).status_code == 200


def test_mesmo_com_modulos_habilitados_recepcao_nao_acessa_prontuario(
    clinica_a, orcamento, criar_usuario, cliente_de
):
    configurar(clinica_a, {"odontologia", "medicina"})
    cliente = cliente_de(criar_usuario("recepcao_sem_prontuario", clinica_a, Papel.RECEPCAO))
    assert cliente.get(reverse("prontuario:novo", args=[orcamento.paciente_id])).status_code == 403


def test_modulos_nao_habilitam_cadastro_de_segunda_clinica(
    clinica_a, django_user_model, cliente_de
):
    configurar(clinica_a, {"odontologia", "medicina"})
    cliente = cliente_de(django_user_model.objects.create_superuser("root_modulos"))
    assert (
        cliente.post(
            reverse("cadastrar_clinica"), {"nome": "Outra clínica fictícia", "area": "medicina"}
        ).status_code
        == 302
    )
    assert Clinica.objects.count() == 1
