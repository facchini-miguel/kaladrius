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
from apps.core.forms import ClinicAdminForm, ClinicForm
from apps.core.isolation import NoCurrentClinic, WrongClinic, use_clinic
from apps.core.models import GENERAL_MODULES, Clinic, ClinicModule, ModuleCode, Role
from apps.core.modules import configure
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
        "modules": ["odontologia", "medicina"],
        "general_modules": sorted(GENERAL_MODULES),
        **extra,
    }


@pytest.mark.parametrize("area", Clinic.Area.values)
def test_creation_keeps_original_area_capability(area):
    clinic = Clinic.objects.create(name="Clínica fictícia", area=area)
    assert clinic.dentistry == (area == "odontologia")
    assert clinic.medicine == (area == "medicina")
    with use_clinic(clinic):
        assert ClinicModule.objects.count() == len(ModuleCode)


@pytest.mark.parametrize(
    "codigos", [[], ["medicina"], ["odontologia"], ["odontologia", "medicina"]]
)
def test_admin_sets_independent_areas(codigos, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_modulos", clinica_a, Role.ADMIN))
    response = cliente.post(reverse("clinic_settings"), config(modules=codigos))
    assert response.status_code == 302
    clinica_a.refresh_from_db()
    assert clinica_a.area == "medicina"  # primary area does not dictate enabled modules
    assert clinica_a.dentistry == ("odontologia" in codigos)
    assert clinica_a.medicine == ("medicina" in codigos)


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.PRACTITIONER, Role.FINANCE])
def test_other_roles_do_not_change_modules(role, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("usuario_modulos", clinica_a, role))
    assert cliente.post(reverse("clinic_settings"), config()).status_code == 403
    assert clinica_a.dentistry and not clinica_a.medicine


def test_demo_admin_does_not_change_modules(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("demo_modulos", clinica_a, Role.ADMIN, demo=True))
    assert cliente.post(reverse("clinic_settings"), config()).status_code == 403
    assert not clinica_a.medicine


def test_unknown_module_saved_neither_in_service_nor_form(clinica_a):
    with pytest.raises(ValidationError):
        configure(clinica_a, {"desconhecido"})
    form = ClinicForm(config(modules=["desconhecido"]), instance=clinica_a)
    assert not form.is_valid() and "modules" in form.errors
    assert clinica_a.dentistry and not clinica_a.module_enabled("desconhecido")


def test_modules_are_isolated_and_query_without_clinic_fails(clinica_a, clinica_b):
    configure(clinica_b, {*GENERAL_MODULES, "medicina"})
    with use_clinic(clinica_a):
        assert set(ClinicModule.objects.values_list("clinic_id", flat=True)) == {clinica_a.pk}
    with pytest.raises(NoCurrentClinic):
        ClinicModule.objects.count()
    assert clinica_a.dentistry and not clinica_b.dentistry


def test_idempotent_reconfiguration_keeps_ids_and_logs_change(clinica_a):
    before = dict(ClinicModule.all_objects.filter(clinic=clinica_a).values_list("code", "pk"))
    configure(clinica_a, {*GENERAL_MODULES, "medicina"})
    after = dict(ClinicModule.all_objects.filter(clinic=clinica_a).values_list("code", "pk"))
    assert before == after
    changes = AuditEntry.objects.filter(
        clinic=clinica_a, model_name="Módulo da clínica", action=AuditEntry.Action.CHANGE
    )
    assert changes.count() == 2
    configure(clinica_a, {*GENERAL_MODULES, "medicina"})
    assert changes.count() == 2


def test_admin_fields_and_commit_false_kept(clinica_a):
    form = ClinicAdminForm(config(active="on"), instance=clinica_a)
    assert "active" in form.fields and "modules" in form.fields
    assert form.is_valid(), form.errors
    clinic = form.save(commit=False)
    assert not clinic.medicine
    clinic.save()
    form.save_m2m()
    assert clinic.medicine and clinic.dentistry


def test_django_admin_saves_modules_and_audits_superuser(clinica_a, django_user_model, cliente_de):
    user = django_user_model.objects.create_superuser("root_config_ficticio")
    cliente = cliente_de(user)
    url = reverse("admin:core_clinic_change", args=[clinica_a.pk])
    page = cliente.get(url)
    assert page.status_code == 200
    assert set(page.context["adminform"].form.initial["modules"]) == {"odontologia"}
    prefixo = page.context["inline_admin_formsets"][0].formset.prefix
    response = cliente.post(
        url,
        config(
            active="on",
            modules=["medicina"],
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
    assert clinica_a.medicine and not clinica_a.dentistry
    assert (
        AuditEntry.objects.filter(
            clinic=clinica_a,
            user=user,
            model_name="Módulo da clínica",
            action=AuditEntry.Action.CHANGE,
        ).count()
        == 2
    )
    assert cliente.get(reverse("admin:core_clinic_add")).status_code == 403


def test_admin_schedule_validation_considers_only_edited_clinic(
    clinica_a, clinica_b, criar_profissional, django_user_model, cliente_de
):
    practitioner = criar_profissional(clinica_b, "Profissional fictício B")
    start = timezone.localtime(timezone.now() + datetime.timedelta(days=2)).replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    with use_clinic(clinica_b):
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
    with use_clinic(clinica_a):
        patient = Patient.objects.create(name="Paciente inteiramente fictício")
        return Estimate.objects.create(patient=patient)


def novo_item(estimate, **extra):
    return EstimateItem(
        estimate=estimate,
        description="Procedimento fictício",
        unit_price=Decimal("10"),
        **extra,
    )


def test_detail_does_not_query_modules_per_item(clinica_a, estimate, criar_usuario, cliente_de):
    with use_clinic(clinica_a):
        for _ in range(4):
            novo_item(estimate, teeth="11").save()
    cliente = cliente_de(criar_usuario("recepcao_consultas", clinica_a, Role.FRONT_DESK))
    with CaptureQueriesContext(connection) as consultas:
        response = cliente.get(reverse("estimates:detail", args=[estimate.pk]))
    assert response.status_code == 200
    assert response.context["dentistry_enabled"]
    consultas_modulos = [q for q in consultas if 'FROM "core_clinic_module"' in q["sql"]]
    assert len(consultas_modulos) <= 2


def test_model_blocks_teeth_without_relying_on_screen(clinica_a, estimate):
    configure(clinica_a, {*GENERAL_MODULES, "medicina"})
    with use_clinic(clinica_a):
        with pytest.raises(ValidationError):
            novo_item(estimate, teeth="11").save()
        novo_item(estimate).save()  # general estimates remain available
        assert EstimateItem.objects.count() == 1


def test_dental_history_stays_readable_and_not_editable(clinica_a, estimate):
    with use_clinic(clinica_a):
        item = novo_item(estimate, teeth="11", faces="V")
        item.save()
    configure(clinica_a, {*GENERAL_MODULES, "medicina"})
    with use_clinic(clinica_a):
        assert EstimateItem.objects.get().teeth == "11"
        item.teeth = item.faces = ""
        with pytest.raises(ValidationError):
            item.save()
        with pytest.raises(ValidationError):
            item.delete()
    configure(clinica_a, {*GENERAL_MODULES, "odontologia", "medicina"})
    with use_clinic(clinica_a):
        item.refresh_from_db()
        item.delete()


def test_http_does_not_remove_history_when_module_off(
    clinica_a, estimate, criar_usuario, cliente_de
):
    with use_clinic(clinica_a):
        item = novo_item(estimate, faces="Arcada superior")
        item.save()
    configure(clinica_a, {*GENERAL_MODULES, "medicina"})
    cliente = cliente_de(criar_usuario("recepcao_modulos", clinica_a, Role.FRONT_DESK))
    detalhe = cliente.get(reverse("estimates:detail", args=[estimate.pk]))
    assert detalhe.status_code == 200 and detalhe.context["show_teeth"]
    assert "Arcada superior" in detalhe.content.decode()
    assert (
        cliente.post(reverse("estimates:item_remove", args=[estimate.pk, item.pk])).status_code
        == 403
    )
    with use_clinic(clinica_a):
        assert EstimateItem.objects.filter(pk=item.pk).exists()


def test_item_cannot_link_estimate_of_another_clinic(clinica_b, estimate):
    with use_clinic(clinica_b), pytest.raises(WrongClinic):
        novo_item(estimate, teeth="11").save()


@pytest.mark.parametrize("codigos", [[], ["medicina"], ["odontologia", "medicina"]])
def test_common_record_does_not_require_specialized_module(
    codigos, clinica_a, estimate, criar_usuario, cliente_de
):
    configure(clinica_a, {*GENERAL_MODULES, *codigos})
    user = criar_usuario("prof_modulos", clinica_a, Role.PRACTITIONER)
    with use_clinic(clinica_a):
        Practitioner.objects.create(name="Profissional fictício", user=user)
    cliente = cliente_de(user)
    assert (
        cliente.get(reverse("medical_records:new", args=[estimate.patient_id])).status_code == 200
    )


def test_even_with_modules_on_reception_cannot_access_records(
    clinica_a, estimate, criar_usuario, cliente_de
):
    configure(clinica_a, {*GENERAL_MODULES, "odontologia", "medicina"})
    cliente = cliente_de(criar_usuario("recepcao_sem_prontuario", clinica_a, Role.FRONT_DESK))
    assert (
        cliente.get(reverse("medical_records:new", args=[estimate.patient_id])).status_code == 403
    )


def test_modules_do_not_enable_second_clinic_registration(clinica_a, django_user_model, cliente_de):
    configure(clinica_a, {*GENERAL_MODULES, "odontologia", "medicina"})
    cliente = cliente_de(django_user_model.objects.create_superuser("root_modulos"))
    assert (
        cliente.post(
            reverse("register_clinic"), {"name": "Outra clínica fictícia", "area": "medicina"}
        ).status_code
        == 302
    )
    assert Clinic.objects.count() == 1


def test_superuser_uses_odontogram_with_dentistry_off(
    clinica_a, estimate, criar_usuario, django_user_model, cliente_de
):
    """Decision 115: the system administrator still uses a turned-off specialty, marked as off;
    the team cannot."""
    configure(clinica_a, {*GENERAL_MODULES, "medicina"})
    item_dental = {
        "description": "Restauração fictícia",
        "teeth": "36",
        "faces": "O",
        "quantity": 1,
        "unit_price": "100",
    }
    adicionar = reverse("estimates:item_add", args=[estimate.pk])

    admin = cliente_de(criar_usuario("admin_odonto", clinica_a, Role.ADMIN))
    admin.post(adicionar, item_dental)
    with use_clinic(clinica_a):
        assert not EstimateItem.objects.filter(teeth="36").exists()

    root = cliente_de(django_user_model.objects.create_superuser("root_odonto"))
    detalhe = root.get(reverse("estimates:detail", args=[estimate.pk]))
    assert detalhe.context["show_teeth"]
    assert "O módulo Odontologia está desligado nesta clínica" in detalhe.content.decode()
    root.post(adicionar, item_dental)
    with use_clinic(clinica_a):
        item = EstimateItem.objects.get(teeth="36")
    root.post(reverse("estimates:item_remove", args=[estimate.pk, item.pk]))
    with use_clinic(clinica_a):
        assert not EstimateItem.objects.filter(pk=item.pk).exists()
