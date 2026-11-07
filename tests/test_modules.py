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
        "area": "medicine",
        "schedule_start": "07:30",
        "schedule_end": "20:00",
        "currency": "BRL",
        "schedule_interval": 30,
        "modules": ["dentistry", "medicine"],
        "general_modules": sorted(GENERAL_MODULES),
        **extra,
    }


@pytest.mark.parametrize("area", Clinic.Area.values)
def test_creation_keeps_original_area_capability(area):
    clinic = Clinic.objects.create(name="Clínica fictícia", area=area)
    assert clinic.dentistry == (area == "dentistry")
    assert clinic.medicine == (area == "medicine")
    with use_clinic(clinic):
        assert ClinicModule.objects.count() == len(ModuleCode)


@pytest.mark.parametrize("codes", [[], ["medicine"], ["dentistry"], ["dentistry", "medicine"]])
def test_admin_sets_independent_areas(codes, clinic_a, create_user, client_for):
    user_client = client_for(create_user("admin_modulos", clinic_a, Role.ADMIN))
    response = user_client.post(reverse("clinic_settings"), config(modules=codes))
    assert response.status_code == 302
    clinic_a.refresh_from_db()
    assert clinic_a.area == "medicine"  # primary area does not dictate enabled modules
    assert clinic_a.dentistry == ("dentistry" in codes)
    assert clinic_a.medicine == ("medicine" in codes)


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.PRACTITIONER, Role.FINANCE])
def test_other_roles_do_not_change_modules(role, clinic_a, create_user, client_for):
    user_client = client_for(create_user("usuario_modulos", clinic_a, role))
    assert user_client.post(reverse("clinic_settings"), config()).status_code == 403
    assert clinic_a.dentistry and not clinic_a.medicine


def test_demo_admin_does_not_change_modules(clinic_a, create_user, client_for):
    user_client = client_for(create_user("demo_modulos", clinic_a, Role.ADMIN, demo=True))
    assert user_client.post(reverse("clinic_settings"), config()).status_code == 403
    assert not clinic_a.medicine


def test_unknown_module_saved_neither_in_service_nor_form(clinic_a):
    with pytest.raises(ValidationError):
        configure(clinic_a, {"desconhecido"})
    form = ClinicForm(config(modules=["desconhecido"]), instance=clinic_a)
    assert not form.is_valid() and "modules" in form.errors
    assert clinic_a.dentistry and not clinic_a.module_enabled("desconhecido")


def test_modules_are_isolated_and_query_without_clinic_fails(clinic_a, clinic_b):
    configure(clinic_b, {*GENERAL_MODULES, "medicine"})
    with use_clinic(clinic_a):
        assert set(ClinicModule.objects.values_list("clinic_id", flat=True)) == {clinic_a.pk}
    with pytest.raises(NoCurrentClinic):
        ClinicModule.objects.count()
    assert clinic_a.dentistry and not clinic_b.dentistry


def test_idempotent_reconfiguration_keeps_ids_and_logs_change(clinic_a):
    before = dict(ClinicModule.all_objects.filter(clinic=clinic_a).values_list("code", "pk"))
    configure(clinic_a, {*GENERAL_MODULES, "medicine"})
    after = dict(ClinicModule.all_objects.filter(clinic=clinic_a).values_list("code", "pk"))
    assert before == after
    changes = AuditEntry.objects.filter(
        clinic=clinic_a, model_name="Módulo da clínica", action=AuditEntry.Action.CHANGE
    )
    assert changes.count() == 2
    configure(clinic_a, {*GENERAL_MODULES, "medicine"})
    assert changes.count() == 2


def test_admin_fields_and_commit_false_kept(clinic_a):
    form = ClinicAdminForm(config(active="on"), instance=clinic_a)
    assert "active" in form.fields and "modules" in form.fields
    assert form.is_valid(), form.errors
    clinic = form.save(commit=False)
    assert not clinic.medicine
    clinic.save()
    form.save_m2m()
    assert clinic.medicine and clinic.dentistry


def test_django_admin_saves_modules_and_audits_superuser(clinic_a, django_user_model, client_for):
    user = django_user_model.objects.create_superuser("root_config_ficticio")
    user_client = client_for(user)
    url = reverse("admin:core_clinic_change", args=[clinic_a.pk])
    page = user_client.get(url)
    assert page.status_code == 200
    assert set(page.context["adminform"].form.initial["modules"]) == {"dentistry"}
    prefix = page.context["inline_admin_formsets"][0].formset.prefix
    response = user_client.post(
        url,
        config(
            active="on",
            modules=["medicine"],
            **{
                f"{prefix}-TOTAL_FORMS": "0",
                f"{prefix}-INITIAL_FORMS": "0",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1000",
                "_save": "Salvar",
            },
        ),
    )
    assert response.status_code == 302
    assert clinic_a.medicine and not clinic_a.dentistry
    assert (
        AuditEntry.objects.filter(
            clinic=clinic_a,
            user=user,
            model_name="Módulo da clínica",
            action=AuditEntry.Action.CHANGE,
        ).count()
        == 2
    )
    assert user_client.get(reverse("admin:core_clinic_add")).status_code == 403


def test_admin_schedule_validation_considers_only_edited_clinic(
    clinic_a, clinic_b, create_practitioner, django_user_model, client_for
):
    practitioner = create_practitioner(clinic_b, "Profissional fictício B")
    start = timezone.localtime(timezone.now() + datetime.timedelta(days=2)).replace(
        hour=6, minute=0, second=0, microsecond=0
    )
    with use_clinic(clinic_b):
        Appointment.objects.create(
            practitioner=practitioner,
            kind=AppointmentType.objects.first(),
            start=start,
            end=start + datetime.timedelta(minutes=30),
        )
    user_client = client_for(django_user_model.objects.create_superuser("root_agenda_ficticio"))
    url = reverse("admin:core_clinic_change", args=[clinic_a.pk])
    form = user_client.get(url).context["adminform"].form
    form = type(form)(config(active="on"), instance=clinic_a)
    assert form.is_valid(), form.errors
    other = type(form)(config(active="on"), instance=clinic_b)
    assert not other.is_valid()
    assert "Ajuste os agendamentos futuros" in str(other.non_field_errors())


@pytest.fixture
def estimate(clinic_a):
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="Paciente inteiramente fictício")
        return Estimate.objects.create(patient=patient)


def new_item(estimate, **extra):
    return EstimateItem(
        estimate=estimate,
        description="Procedimento fictício",
        unit_price=Decimal("10"),
        **extra,
    )


def test_detail_does_not_query_modules_per_item(clinic_a, estimate, create_user, client_for):
    with use_clinic(clinic_a):
        for _ in range(4):
            new_item(estimate, teeth="11").save()
    user_client = client_for(create_user("recepcao_consultas", clinic_a, Role.FRONT_DESK))
    with CaptureQueriesContext(connection) as queries:
        response = user_client.get(reverse("estimates:detail", args=[estimate.pk]))
    assert response.status_code == 200
    assert response.context["dentistry_enabled"]
    module_queries = [q for q in queries if 'FROM "core_clinic_module"' in q["sql"]]
    assert len(module_queries) <= 2


def test_model_blocks_teeth_without_relying_on_screen(clinic_a, estimate):
    configure(clinic_a, {*GENERAL_MODULES, "medicine"})
    with use_clinic(clinic_a):
        with pytest.raises(ValidationError):
            new_item(estimate, teeth="11").save()
        new_item(estimate).save()  # general estimates remain available
        assert EstimateItem.objects.count() == 1


def test_dental_history_stays_readable_and_not_editable(clinic_a, estimate):
    with use_clinic(clinic_a):
        item = new_item(estimate, teeth="11", faces="V")
        item.save()
    configure(clinic_a, {*GENERAL_MODULES, "medicine"})
    with use_clinic(clinic_a):
        assert EstimateItem.objects.get().teeth == "11"
        item.teeth = item.faces = ""
        with pytest.raises(ValidationError):
            item.save()
        with pytest.raises(ValidationError):
            item.delete()
    configure(clinic_a, {*GENERAL_MODULES, "dentistry", "medicine"})
    with use_clinic(clinic_a):
        item.refresh_from_db()
        item.delete()


def test_http_does_not_remove_history_when_module_off(clinic_a, estimate, create_user, client_for):
    with use_clinic(clinic_a):
        item = new_item(estimate, faces="Arcada superior")
        item.save()
    configure(clinic_a, {*GENERAL_MODULES, "medicine"})
    user_client = client_for(create_user("recepcao_modulos", clinic_a, Role.FRONT_DESK))
    detail = user_client.get(reverse("estimates:detail", args=[estimate.pk]))
    assert detail.status_code == 200 and detail.context["show_teeth"]
    assert "Arcada superior" in detail.content.decode()
    assert (
        user_client.post(reverse("estimates:item_remove", args=[estimate.pk, item.pk])).status_code
        == 403
    )
    with use_clinic(clinic_a):
        assert EstimateItem.objects.filter(pk=item.pk).exists()


def test_item_cannot_link_estimate_of_another_clinic(clinic_b, estimate):
    with use_clinic(clinic_b), pytest.raises(WrongClinic):
        new_item(estimate, teeth="11").save()


@pytest.mark.parametrize("codes", [[], ["medicine"], ["dentistry", "medicine"]])
def test_common_record_does_not_require_specialized_module(
    codes, clinic_a, estimate, create_user, client_for
):
    configure(clinic_a, {*GENERAL_MODULES, *codes})
    user = create_user("prof_modulos", clinic_a, Role.PRACTITIONER)
    with use_clinic(clinic_a):
        Practitioner.objects.create(name="Profissional fictício", user=user)
    user_client = client_for(user)
    assert (
        user_client.get(reverse("medical_records:new", args=[estimate.patient_id])).status_code
        == 200
    )


def test_even_with_modules_on_reception_cannot_access_records(
    clinic_a, estimate, create_user, client_for
):
    configure(clinic_a, {*GENERAL_MODULES, "dentistry", "medicine"})
    user_client = client_for(create_user("recepcao_sem_prontuario", clinic_a, Role.FRONT_DESK))
    assert (
        user_client.get(reverse("medical_records:new", args=[estimate.patient_id])).status_code
        == 403
    )


def test_modules_do_not_enable_second_clinic_registration(clinic_a, django_user_model, client_for):
    configure(clinic_a, {*GENERAL_MODULES, "dentistry", "medicine"})
    user_client = client_for(django_user_model.objects.create_superuser("root_modulos"))
    assert (
        user_client.post(
            reverse("register_clinic"), {"name": "Outra clínica fictícia", "area": "medicine"}
        ).status_code
        == 302
    )
    assert Clinic.objects.count() == 1


def test_superuser_uses_odontogram_with_dentistry_off(
    clinic_a, estimate, create_user, django_user_model, client_for
):
    """Decision 115: the system administrator still uses a turned-off specialty, marked as off;
    the team cannot."""
    configure(clinic_a, {*GENERAL_MODULES, "medicine"})
    item_dental = {
        "description": "Restauração fictícia",
        "teeth": "36",
        "faces": "O",
        "quantity": 1,
        "unit_price": "100",
    }
    add = reverse("estimates:item_add", args=[estimate.pk])

    admin = client_for(create_user("admin_odonto", clinic_a, Role.ADMIN))
    admin.post(add, item_dental)
    with use_clinic(clinic_a):
        assert not EstimateItem.objects.filter(teeth="36").exists()

    root = client_for(django_user_model.objects.create_superuser("root_odonto"))
    detail = root.get(reverse("estimates:detail", args=[estimate.pk]))
    assert detail.context["show_teeth"]
    assert "O módulo Odontologia está desligado nesta clínica" in detail.content.decode()
    root.post(add, item_dental)
    with use_clinic(clinic_a):
        item = EstimateItem.objects.get(teeth="36")
    root.post(reverse("estimates:item_remove", args=[estimate.pk, item.pk]))
    with use_clinic(clinic_a):
        assert not EstimateItem.objects.filter(pk=item.pk).exists()
