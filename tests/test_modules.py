"""Specialties are configured independently, using fictitious patients only."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEntry
from apps.core.forms import ClinicaAdminForm, ClinicaForm
from apps.core.isolation import ClinicaDiferente, SemClinicaAtual, usar_clinica
from apps.core.models import MODULOS_GERAIS, Clinic, ClinicModule, ModuloClinico, Papel
from apps.core.modules import configurar
from apps.estimates.models import Estimate, EstimateItem
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db


def config(**extra):
    return {
        "name": "Clínica fictícia",
        "area": "medicina",
        "schedule_start": "07:30",
        "schedule_end": "20:00",
        "currency": "BRL",
        "schedule_interval": 30,
        "modulos": ["odontologia", "medicina"],
        "modulos_gerais": sorted(MODULOS_GERAIS),
        **extra,
    }


@pytest.mark.parametrize("area", Clinic.Area.values)
def test_criacao_preserva_a_capacidade_da_area_original(area):
    clinic = Clinic.objects.create(name="Clínica fictícia", area=area)
    assert clinic.odontologia == (area == "odontologia")
    assert clinic.medicina == (area == "medicina")
    with usar_clinica(clinic):
        assert ClinicModule.objects.count() == len(ModuloClinico)


@pytest.mark.parametrize(
    "codigos", [[], ["medicina"], ["odontologia"], ["odontologia", "medicina"]]
)
def test_admin_configura_areas_independentes(codigos, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_modulos", clinica_a, Papel.ADMIN))
    response = cliente.post(reverse("clinic_settings"), config(modulos=codigos))
    assert response.status_code == 302
    clinica_a.refresh_from_db()
    assert clinica_a.area == "medicina"  # primary area does not dictate enabled modules
    assert clinica_a.odontologia == ("odontologia" in codigos)
    assert clinica_a.medicina == ("medicina" in codigos)


@pytest.mark.parametrize("role", [Papel.RECEPCAO, Papel.PROFISSIONAL, Papel.FINANCEIRO])
def test_outros_papeis_nao_alteram_modulos(role, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario_modulos", clinica_a, role))
    assert cliente.post(reverse("clinic_settings"), config()).status_code == 403
    assert clinica_a.odontologia and not clinica_a.medicina


def test_administrador_de_demo_nao_altera_modulos(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("demo_modulos", clinica_a, Papel.ADMIN, demo=True))
    assert cliente.post(reverse("clinic_settings"), config()).status_code == 403
    assert not clinica_a.medicina


def test_modulo_desconhecido_nao_grava_nem_no_servico_nem_no_form(clinica_a):
    with pytest.raises(ValidationError):
        configurar(clinica_a, {"desconhecido"})
    form = ClinicaForm(config(modulos=["desconhecido"]), instance=clinica_a)
    assert not form.is_valid() and "modulos" in form.errors
    assert clinica_a.odontologia and not clinica_a.modulo_habilitado("desconhecido")


def test_modulos_sao_isolados_e_a_consulta_sem_clinica_falha(clinica_a, clinica_b):
    configurar(clinica_b, {*MODULOS_GERAIS, "medicina"})
    with usar_clinica(clinica_a):
        assert set(ClinicModule.objects.values_list("clinic_id", flat=True)) == {clinica_a.pk}
    with pytest.raises(SemClinicaAtual):
        ClinicModule.objects.count()
    assert clinica_a.odontologia and not clinica_b.odontologia


def test_reconfiguracao_idempotente_preserva_ids_e_registra_mudanca(clinica_a):
    before = dict(ClinicModule.todos.filter(clinic=clinica_a).values_list("code", "pk"))
    configurar(clinica_a, {*MODULOS_GERAIS, "medicina"})
    after = dict(ClinicModule.todos.filter(clinic=clinica_a).values_list("code", "pk"))
    assert before == after
    changes = AuditEntry.objects.filter(
        clinic=clinica_a, model_name="Módulo da clínica", action=AuditEntry.Acao.ALTERAR
    )
    assert changes.count() == 2
    configurar(clinica_a, {*MODULOS_GERAIS, "medicina"})
    assert changes.count() == 2


def test_campos_administrativos_e_commit_false_preservados(clinica_a):
    form = ClinicaAdminForm(config(active="on"), instance=clinica_a)
    assert "active" in form.fields and "modulos" in form.fields
    assert form.is_valid(), form.errors
    clinic = form.save(commit=False)
    assert not clinic.medicina
    clinic.save()
    form.save_m2m()
    assert clinic.medicina and clinic.odontologia


def test_django_admin_salva_modulos_e_audita_o_superusuario(
    clinica_a, django_user_model, cliente_de
):
    user = django_user_model.objects.create_superuser("root_config_ficticio")
    cliente = cliente_de(user)
    url = reverse("admin:core_clinic_change", args=[clinica_a.pk])
    page = cliente.get(url)
    assert page.status_code == 200
    assert set(page.context["adminform"].form.initial["modulos"]) == {"odontologia"}
    prefixo = page.context["inline_admin_formsets"][0].formset.prefix
    response = cliente.post(
        url,
        config(
            active="on",
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
    assert response.status_code == 302
    assert clinica_a.medicina and not clinica_a.odontologia
    assert (
        AuditEntry.objects.filter(
            clinic=clinica_a,
            user=user,
            model_name="Módulo da clínica",
            action=AuditEntry.Acao.ALTERAR,
        ).count()
        == 2
    )
    assert cliente.get(reverse("admin:core_clinic_add")).status_code == 403


def test_validacao_da_agenda_no_admin_considera_so_a_clinica_editada(
    clinica_a, clinica_b, criar_profissional, django_user_model, cliente_de
):
    practitioner = criar_profissional(clinica_b, "Profissional fictício B")
    start = timezone.localtime(timezone.now() + datetime.timedelta(days=2)).replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    with usar_clinica(clinica_b):
        Appointment.objects.create(
            practitioner=practitioner,
            kind=AppointmentType.objects.first(),
            start=start,
            end=start + datetime.timedelta(minutes=30),
        )
    cliente = cliente_de(django_user_model.objects.create_superuser("root_agenda_ficticio"))
    url = reverse("admin:core_clinic_change", args=[clinica_a.pk])
    form = cliente.get(url).context["adminform"].form
    form = type(form)(config(active="on"), instance=clinica_a)
    assert form.is_valid(), form.errors
    other = type(form)(config(active="on"), instance=clinica_b)
    assert not other.is_valid()
    assert "Ajuste os agendamentos futuros" in str(other.non_field_errors())


@pytest.fixture
def estimate(clinica_a):
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(name="Paciente inteiramente fictício")
        return Estimate.objects.create(patient=patient)


def novo_item(estimate, **extra):
    return EstimateItem(
        estimate=estimate,
        description="Procedimento fictício",
        unit_price=Decimal("10"),
        **extra,
    )


def test_detalhe_nao_consulta_modulos_para_cada_item(
    clinica_a, estimate, criar_usuario, cliente_de
):
    with usar_clinica(clinica_a):
        for _ in range(4):
            novo_item(estimate, teeth="11").save()
    cliente = cliente_de(criar_usuario("recepcao_consultas", clinica_a, Papel.RECEPCAO))
    with CaptureQueriesContext(connection) as consultas:
        response = cliente.get(reverse("estimates:detail", args=[estimate.pk]))
    assert response.status_code == 200
    assert response.context["odontologia_habilitada"]
    consultas_modulos = [q for q in consultas if 'FROM "core_modulodaclinica"' in q["sql"]]
    assert len(consultas_modulos) <= 2


def test_modelo_bloqueia_dentes_sem_depender_da_tela(clinica_a, estimate):
    configurar(clinica_a, {*MODULOS_GERAIS, "medicina"})
    with usar_clinica(clinica_a):
        with pytest.raises(ValidationError):
            novo_item(estimate, teeth="11").save()
        novo_item(estimate).save()  # general estimates remain available
        assert EstimateItem.objects.count() == 1


def test_historico_dental_permanece_legivel_e_nao_editavel(clinica_a, estimate):
    with usar_clinica(clinica_a):
        item = novo_item(estimate, teeth="11", faces="V")
        item.save()
    configurar(clinica_a, {*MODULOS_GERAIS, "medicina"})
    with usar_clinica(clinica_a):
        assert EstimateItem.objects.get().teeth == "11"
        item.teeth = item.faces = ""
        with pytest.raises(ValidationError):
            item.save()
        with pytest.raises(ValidationError):
            item.delete()
    configurar(clinica_a, {*MODULOS_GERAIS, "odontologia", "medicina"})
    with usar_clinica(clinica_a):
        item.refresh_from_db()
        item.delete()


def test_http_nao_remove_historico_quando_modulo_desativado(
    clinica_a, estimate, criar_usuario, cliente_de
):
    with usar_clinica(clinica_a):
        item = novo_item(estimate, faces="Arcada superior")
        item.save()
    configurar(clinica_a, {*MODULOS_GERAIS, "medicina"})
    cliente = cliente_de(criar_usuario("recepcao_modulos", clinica_a, Papel.RECEPCAO))
    detalhe = cliente.get(reverse("estimates:detail", args=[estimate.pk]))
    assert detalhe.status_code == 200 and detalhe.context["mostrar_dentes"]
    assert "Arcada superior" in detalhe.content.decode()
    assert (
        cliente.post(reverse("estimates:item_remove", args=[estimate.pk, item.pk])).status_code
        == 403
    )
    with usar_clinica(clinica_a):
        assert EstimateItem.objects.filter(pk=item.pk).exists()


def test_item_nao_pode_vincular_orcamento_de_outra_clinica(clinica_b, estimate):
    with usar_clinica(clinica_b), pytest.raises(ClinicaDiferente):
        novo_item(estimate, teeth="11").save()


@pytest.mark.parametrize("codigos", [[], ["medicina"], ["odontologia", "medicina"]])
def test_prontuario_comum_nao_exige_modulo_especializado(
    codigos, clinica_a, estimate, criar_usuario, cliente_de
):
    configurar(clinica_a, {*MODULOS_GERAIS, *codigos})
    user = criar_usuario("prof_modulos", clinica_a, Papel.PROFISSIONAL)
    with usar_clinica(clinica_a):
        Practitioner.objects.create(name="Profissional fictício", user=user)
    cliente = cliente_de(user)
    assert (
        cliente.get(reverse("medical_records:new", args=[estimate.patient_id])).status_code == 200
    )


def test_mesmo_com_modulos_habilitados_recepcao_nao_acessa_prontuario(
    clinica_a, estimate, criar_usuario, cliente_de
):
    configurar(clinica_a, {*MODULOS_GERAIS, "odontologia", "medicina"})
    cliente = cliente_de(criar_usuario("recepcao_sem_prontuario", clinica_a, Papel.RECEPCAO))
    assert (
        cliente.get(reverse("medical_records:new", args=[estimate.patient_id])).status_code == 403
    )


def test_modulos_nao_habilitam_cadastro_de_segunda_clinica(
    clinica_a, django_user_model, cliente_de
):
    configurar(clinica_a, {*MODULOS_GERAIS, "odontologia", "medicina"})
    cliente = cliente_de(django_user_model.objects.create_superuser("root_modulos"))
    assert (
        cliente.post(
            reverse("register_clinic"), {"name": "Outra clínica fictícia", "area": "medicina"}
        ).status_code
        == 302
    )
    assert Clinic.objects.count() == 1


def test_superusuario_usa_odontograma_com_odontologia_desligada(
    clinica_a, estimate, criar_usuario, django_user_model, cliente_de
):
    """Decision 115: the system administrator still uses a turned-off specialty, marked as off;
    the team cannot."""
    configurar(clinica_a, {*MODULOS_GERAIS, "medicina"})
    item_dental = {
        "description": "Restauração fictícia",
        "teeth": "36",
        "faces": "O",
        "quantity": 1,
        "unit_price": "100",
    }
    adicionar = reverse("estimates:item_add", args=[estimate.pk])

    admin = cliente_de(criar_usuario("admin_odonto", clinica_a, Papel.ADMIN))
    admin.post(adicionar, item_dental)
    with usar_clinica(clinica_a):
        assert not EstimateItem.objects.filter(teeth="36").exists()

    root = cliente_de(django_user_model.objects.create_superuser("root_odonto"))
    detalhe = root.get(reverse("estimates:detail", args=[estimate.pk]))
    assert detalhe.context["mostrar_dentes"]
    assert "O módulo Odontologia está desligado nesta clínica" in detalhe.content.decode()
    root.post(adicionar, item_dental)
    with usar_clinica(clinica_a):
        item = EstimateItem.objects.get(teeth="36")
    root.post(reverse("estimates:item_remove", args=[estimate.pk, item.pk]))
    with usar_clinica(clinica_a):
        assert not EstimateItem.objects.filter(pk=item.pk).exists()
