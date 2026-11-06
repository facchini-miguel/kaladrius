"""Health plans and insurance of each country (decision 125): the insurer's registry, the card's
fields and the procedure coding follow the clinic's country."""

import re

import pytest
from django.urls import reverse

from apps.core.countries import COUNTRIES
from apps.core.isolation import use_clinic
from apps.estimates.models import Procedure
from apps.health_plans import insurance
from apps.health_plans.models import HealthPlan, MemberCard
from tests.test_estimates import add_item, create_estimate, log_in, scenario  # noqa: F401
from tests.test_health_plans import admin, health_plan, patient, plan_card  # noqa: F401

pytestmark = pytest.mark.django_db


def change_country(clinic, country):
    clinic.country = country
    clinic.save()


def test_each_country_has_its_rules():
    assert set(insurance.INSURERS) == set(COUNTRIES)
    for country, rules in insurance.INSURERS.items():
        for code in (rules.registration, rules.procedure):
            if code and code.default:
                # Every format has an example, and the example follows it.
                assert re.fullmatch(code.default, code.example), country


def test_code_cleaned_and_checked():
    cdt = insurance.for_country("US").procedure
    assert cdt.clean_value(" d1110 ") == "D1110"
    with pytest.raises(Exception, match="CDT"):
        cdt.clean_value("1110")
    assert insurance.for_country("BR").registration.clean_value("00.000-2") == "000002"
    assert (
        insurance.for_country("AR").registration.clean_value("1-0040-7") == "100407"
    )  # free format


def test_insurer_registration_by_country(clinic_a, admin):  # noqa: F811
    form = admin.get(reverse("health_plans:new")).context["form"]
    assert str(form.fields["registration"].label) == "Registro da operadora (ANS)"
    change_country(clinic_a, "US")
    form = admin.get(reverse("health_plans:new")).context["form"]
    assert str(form.fields["registration"].label) == "Registro da operadora (Payer ID)"
    assert "dental insurance carriers" in str(form.fields["name"].help_text)
    refused_one = admin.post(
        reverse("health_plans:new"), {"name": "Fictitious Dental", "registration": "1"}
    )
    assert "registration" in refused_one.context["form"].errors
    data = {"name": "Fictitious Dental", "registration": "ab-123", "active": "on"}
    assert admin.post(reverse("health_plans:new"), data).status_code == 302
    with use_clinic(clinic_a):
        assert HealthPlan.objects.get().registration == "AB123"
    assert "Payer ID" in admin.get(reverse("health_plans:list")).content.decode()
    # The United Kingdom has no insurer registry: no field and no column.
    change_country(clinic_a, "GB")
    assert "registration" not in admin.get(reverse("health_plans:new")).context["form"].fields
    assert "Registro da operadora" not in admin.get(reverse("health_plans:list")).content.decode()


def test_card_fields_by_country(clinic_a, patient, health_plan, admin):  # noqa: F811
    url = reverse("health_plans:card_new", args=[patient.pk])
    fields = admin.get(url).context["form"].fields
    assert "group" not in fields and "member_code" not in fields  # Brazil
    change_country(clinic_a, "US")
    fields = admin.get(url).context["form"].fields
    assert str(fields["number"].label) == "Número da carteirinha (Member ID)"
    assert str(fields["group"].label) == "Número do grupo (Group number)"
    assert "member_code" not in fields
    data = plan_card(health_plan, number="W123456789", group="G-100")
    assert admin.post(url, data).status_code == 302
    with use_clinic(clinic_a):
        assert MemberCard.objects.get().group == "G-100"
    patient_record = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "W123456789" in patient_record and "G-100" in patient_record
    change_country(clinic_a, "ZA")
    fields = admin.get(url).context["form"].fields
    assert str(fields["member_code"].label) == "Código do beneficiário (dependant code)"


def test_procedure_code_goes_to_the_estimate(scenario):  # noqa: F811
    clinic = scenario["clinic"]
    user_client = log_in(scenario, "admin")
    url = reverse("estimates:procedure_edit", args=[scenario["restoration"].pk])
    data = {"name": "Restauração", "amount": "250,00", "category": "", "active": "on"}
    form = user_client.get(url).context["form"]
    assert str(form.fields["code"].label) == "Código (TUSS)"
    assert "code" in user_client.post(url, {**data, "code": "123"}).context["form"].errors
    assert user_client.post(url, {**data, "code": "8510.0099"}).status_code == 302
    with use_clinic(clinic):
        assert Procedure.objects.get(name="Restauração").code == "85100099"
    estimate = create_estimate(scenario, user_client)
    add_item(user_client, estimate, procedure=scenario["restoration"].pk)
    with use_clinic(clinic):
        assert estimate.items.get().code == "85100099"
    printed = user_client.get(reverse("estimates:print", args=[estimate.pk])).content.decode()
    assert "85100099 · Restauração" in printed
    # A country without one coding: just "Código", free text.
    change_country(clinic, "UY")
    form = user_client.get(url).context["form"]
    assert str(form.fields["code"].label) == "Código"
