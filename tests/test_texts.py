"""Texts seen by the front desk review (stage 1): no English left in lists, and Portuguese
month names in lowercase as Portuguese writes them."""

import datetime
from decimal import Decimal

import pytest
from django import forms
from django.urls import reverse
from django.utils import translation
from django.utils.formats import date_format

from apps.core.forms import BootstrapForm
from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.core.ordering import alphabetical_key
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db


@pytest.fixture
def reception(clinic_a, create_user, client_for):
    return client_for(create_user("recepcao_textos", clinic_a, Role.FRONT_DESK))


class _Example(BootstrapForm, forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, localize=True, required=False)
    fixed_one = forms.ChoiceField(choices=[("", "- Select an option -"), ("a", "A")])
    grouped = forms.ChoiceField(choices=[("Grupo", [("b", "B")])])


def test_blank_option_of_fixed_lists_becomes_dash():
    form = _Example()
    assert form.fields["fixed_one"].choices == [("", "—"), ("a", "A")]
    assert form.fields["grouped"].choices == [("Grupo", [("b", "B")])]  # untouched


@pytest.mark.parametrize(
    ("language", "typed", "amount"),
    [
        ("pt-br", "1.234.567,89", "1234567.89"),
        ("pt-br", "R$ 1.500,00", "1500.00"),
        ("pt-br", "1.500", "1500"),
        ("pt-br", "1500.50", "1500.50"),
        ("pt-br", "0,5", "0.5"),
        ("es", "12.000,50", "12000.50"),
        ("en", "1,500.00", "1500.00"),
        ("en", "1,500", "1500"),
    ],
)
def test_numbers_with_thousands_separator(language, typed, amount):
    with translation.override(language):
        form = _Example({"fixed_one": "a", "grouped": "b", "amount": typed})
        assert form.is_valid(), form.errors
    assert form.cleaned_data["amount"] == Decimal(amount)


def test_ambiguous_number_is_still_refused():
    with translation.override("pt-br"):
        assert not _Example({"fixed_one": "a", "grouped": "b", "amount": "1,500"}).is_valid()


def test_reception_forms_without_english(clinic_a, reception):
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="Paciente Fictício")
    for url in (
        reverse("patients:new"),
        reverse("patients:related_new", args=[patient.pk]),
    ):
        page = reception.get(url).content.decode()
        assert "Select an option" not in page, url
        assert '<option value="" selected>—</option>' in page, url


def test_months_lowercase_in_portuguese():
    day = datetime.date(2026, 10, 30)
    with translation.override("pt-br"):
        assert date_format(day, "DATE_FORMAT") == "30 de outubro de 2026"
    with translation.override("es"):
        assert date_format(day, "DATE_FORMAT") == "30 de octubre de 2026"


def test_birthday_month_list_starts_capitalized(reception):
    page = reception.get(reverse("patients:birthdays"), {"month": 10}).content.decode()
    assert ">Outubro</option>" in page


def test_alphabetical_order_with_accents_and_lowercase(clinic_a):
    """The Alpine database sorted by bytes: "Água" went after "Zeca" (decision 103)."""
    with use_clinic(clinic_a):
        for name in ("Zeca Fictício", "Érica Fictícia", "ana Fictícia", "Água Fictícia", "Beto"):
            Patient.objects.create(name=name)
        names = list(Patient.objects.values_list("name", flat=True))
    assert names == ["Água Fictícia", "ana Fictícia", "Beto", "Érica Fictícia", "Zeca Fictício"]


def test_alphabetical_key_ignores_accent_and_case():
    names = ["Zeca", "Érica", "ana", "Água", "Beto"]
    assert sorted(names, key=alphabetical_key) == ["Água", "ana", "Beto", "Érica", "Zeca"]


def test_screens_fit_on_a_phone(clinic_a, reception):
    """Review stage 5 (phone, 390 px): the dental chart scrolls in its own box and the
    printed registration sheet stacks its two columns on a narrow screen."""
    from django.template.loader import render_to_string

    from apps.dentistry.teeth import PERMANENT_TEETH, PRIMARY_TEETH

    html = render_to_string(
        "dentistry/_odontogram.html",
        {"permanent_rows": PERMANENT_TEETH, "primary_rows": PRIMARY_TEETH, "interactive": True},
    )
    assert 'class="odontogram-scroll"' in html
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="Paciente Fictício")
    patient_record = reception.get(reverse("patients:print", args=[patient.pk])).content.decode()
    assert 'class="col-12 col-sm-6"' in patient_record and 'class="col-6"' not in patient_record


def test_django_admin_without_english(client, django_user_model):
    """Review (superuser): the admin's action and filter lists showed Django 6.1's
    "- Select an option -" in English."""
    super_user = django_user_model.objects.create_superuser("super_textos", "s@example.com", "x")
    client.force_login(super_user)
    page = client.get(reverse("admin:reference_data_state_changelist")).content.decode()
    assert "Select an option" not in page and "Selecione uma opção" in page


@pytest.mark.parametrize(
    ("language", "header", "title", "health"),
    [
        ("pt-br", "Kaladrius: administração", "Administração", "Saúde do sistema"),
        ("en", "Kaladrius: administration", "Administration", "System health"),
        ("es", "Kaladrius: administración", "Administración", "Salud del sistema"),
    ],
)
def test_admin_titles_follow_the_language(language, header, title, health):
    from django.apps import apps
    from django.contrib import admin

    with translation.override(language):
        assert str(admin.site.site_header) == header
        assert str(admin.site.index_title) == title
        assert str(apps.get_app_config("monitoring").verbose_name) == health
