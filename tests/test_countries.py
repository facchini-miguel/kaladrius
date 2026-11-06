"""The clinic's country (decision 117): time zone, phones, postal codes, the English variant of
dates and the Brazilian-only fields. Brazil keeps every rule it had (the other test files)."""

import datetime
import re
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone, translation

from apps.core import countries
from apps.core.isolation import use_clinic
from apps.core.middleware import CurrentClinicMiddleware
from apps.core.models import Role
from apps.core.validators import normalize_phone
from apps.patients.models import Patient
from tests.test_core import clinic_data

pytestmark = pytest.mark.django_db


def in_country(clinic, country, **extra):
    clinic.country = country
    clinic.time_zone = extra.pop("fuso", countries.COUNTRIES[country].time_zones[0])
    for field, value in extra.items():
        setattr(clinic, field, value)
    clinic.save()
    return clinic


# --- Phones ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("country", "typed", "kept", "shown", "whatsapp"),
    [
        ("US", "(212) 555-0147", "2125550147", "(212) 555-0147", "https://wa.me/12125550147"),
        ("US", "+1 212 555 0147", "2125550147", "(212) 555-0147", "https://wa.me/12125550147"),
        ("CA", "416-555-0199", "4165550199", "(416) 555-0199", "https://wa.me/14165550199"),
        ("GB", "07700 900123", "7700900123", "07700 900123", "https://wa.me/447700900123"),
        ("GB", "+44 20 7946 0018", "2079460018", "020 7946 0018", "https://wa.me/442079460018"),
        ("AU", "0412 345 678", "412345678", "0412 345 678", "https://wa.me/61412345678"),
        ("AU", "(02) 9876 5432", "298765432", "(02) 9876 5432", "https://wa.me/61298765432"),
        ("ZA", "082 555 1234", "825551234", "082 555 1234", "https://wa.me/27825551234"),
        ("ZA", "0027 82 555 1234", "825551234", "082 555 1234", "https://wa.me/27825551234"),
    ],
)
def test_phone_of_each_country(country, typed, kept, shown, whatsapp):
    assert normalize_phone(typed, country) == kept
    assert countries.format_phone(kept, country) == shown
    assert countries.whatsapp_link(kept, country) == whatsapp


@pytest.mark.parametrize(
    ("country", "typed"),
    [("US", "555-0147"), ("US", "(112) 555-0147"), ("GB", "07700 900"), ("AU", "0612 345 678")],
)
def test_invalid_phone_in_the_country(country, typed):
    with pytest.raises(ValidationError):
        normalize_phone(typed, country)


def test_brazilian_phone_stays_the_same(clinic_a):
    with use_clinic(clinic_a):
        assert normalize_phone("(48) 8888-7777") == "48988887777"  # ninth digit added


# --- Postal codes ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("country", "typed", "kept", "shown"),
    [
        ("BR", "88015-100", "88015100", "88015-100"),
        ("US", "10001", "10001", "10001"),
        ("US", "10001-1234", "100011234", "10001-1234"),
        ("CA", "m5v 3l9", "M5V3L9", "M5V 3L9"),
        ("GB", "sw1a1aa", "SW1A1AA", "SW1A 1AA"),
        ("AU", "2000", "2000", "2000"),
        ("ZA", "8001", "8001", "8001"),
    ],
)
def test_postal_code_of_each_country(country, typed, kept, shown):
    assert countries.normalize_postal_code(typed, country) == kept
    assert countries.format_postal_code(kept, country) == shown


@pytest.mark.parametrize(("country", "typed"), [("US", "1000"), ("CA", "12345"), ("GB", "XYZ")])
def test_invalid_postal_code(country, typed):
    with pytest.raises(ValidationError):
        countries.normalize_postal_code(typed, country)


# --- Time zone and the English variant -------------------------------------------


def _during_request(user):
    """Time zone and language active while a request of `usuario` runs."""
    seen = {}

    def response(request):
        seen["fuso"] = timezone.get_current_timezone_name()
        seen["language"] = translation.get_language()
        return HttpResponse()

    request = RequestFactory().get("/")
    request.user = user
    CurrentClinicMiddleware(response)(request)
    return seen


def test_country_time_zone_and_english_during_the_request(clinic_a, create_user):
    user = create_user("recepcao_londres", clinic_a, Role.FRONT_DESK)
    in_country(clinic_a, "GB")
    with translation.override("en"):
        assert _during_request(user) == {"fuso": "Europe/London", "language": "en-gb"}
    with translation.override("pt-br"):  # only English has country variants
        assert _during_request(user)["language"] == "pt-br"
    in_country(clinic_a, "US", time_zone="America/Chicago")
    with translation.override("en"):
        assert _during_request(user) == {"fuso": "America/Chicago", "language": "en"}
    assert timezone.get_current_timezone_name() == "America/Sao_Paulo"  # deactivated afterwards


def test_dates_in_british_english_and_uk_flag(clinic_a, create_user, client_for):
    in_country(clinic_a, "GB")
    user_client = client_for(create_user("admin_londres", clinic_a, Role.ADMIN))
    user_client.post(reverse("change_language"), {"language": "en"})
    page = user_client.get(reverse("home")).content.decode()
    assert '<html lang="en-gb">' in page
    # The English flag, with or without the hash of the collected static files (CI).
    assert re.search(r"flags/en(\.[0-9a-f]+)?\.svg", page) and "Patients" in page
    with use_clinic(clinic_a):
        patient = Patient.objects.create(
            name="Amelia Fictícia", birth_date=datetime.date(2000, 12, 25)
        )
    patient_record = user_client.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "25/12/2000" in patient_record and "12/25/2000" not in patient_record
    in_country(clinic_a, "US")
    assert (
        "12/25/2000"
        in user_client.get(reverse("patients:record", args=[patient.pk])).content.decode()
    )


# --- Clinic settings -------------------------------------------------------------


def test_changing_country_sets_time_zone_and_currency(clinic_a, create_user, client_for):
    admin = client_for(create_user("admin_pais", clinic_a, Role.ADMIN))
    assert admin.post(reverse("clinic_settings"), clinic_data(country="GB")).status_code == 302
    clinic_a.refresh_from_db()
    assert (clinic_a.country, clinic_a.time_zone, clinic_a.currency) == (
        "GB",
        "Europe/London",
        "GBP",
    )
    # The document is the new country's (decision 121).
    assert admin.get(reverse("clinic_settings")).context["form"]["document"].label == (
        "Company number"
    )

    # A currency chosen on purpose is kept when the country changes.
    data = clinic_data(country="AU", currency="USD", time_zone="Australia/Perth")
    assert admin.post(reverse("clinic_settings"), data).status_code == 302
    clinic_a.refresh_from_db()
    assert (clinic_a.country, clinic_a.time_zone, clinic_a.currency) == (
        "AU",
        "Australia/Perth",
        "USD",
    )


def test_time_zone_of_another_country_is_refused(clinic_a, create_user, client_for):
    admin = client_for(create_user("admin_fuso", clinic_a, Role.ADMIN))
    response = admin.post(
        reverse("clinic_settings"), clinic_data(country="ZA", time_zone="America/New_York")
    )
    assert response.status_code == 200 and "time_zone" in response.context["form"].errors


# --- Patients outside Brazil -----------------------------------------------------


def test_patient_outside_brazil(clinic_a, create_user, client_for):
    in_country(clinic_a, "GB")
    admin = client_for(create_user("admin_paciente", clinic_a, Role.ADMIN))
    form_page = admin.get(reverse("patients:new")).content.decode()
    assert 'data-label-pf="NHS number"' in form_page and 'name="rg"' not in form_page
    assert 'name="state"' not in form_page and 'name="city_name"' in form_page
    assert "Código postal" in form_page

    response = admin.post(
        reverse("patients:new"),
        {
            "kind": "PF",
            "name": "Oliver Fictício",
            "active": "on",
            "mobile_phone": "07700 900123",
            "whatsapp": "+44 7700 900123",
            "postal_code": "sw1a 1aa",
            "city_name": "London",
            "state_name": "England",
        },
    )
    assert response.status_code == 302
    with use_clinic(clinic_a):
        patient = Patient.objects.get(name="Oliver Fictício")
    assert (patient.mobile_phone, patient.whatsapp, patient.postal_code) == (
        "7700900123",
        "7700900123",
        "SW1A1AA",
    )
    patient_record = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "London, England" in patient_record and "SW1A 1AA" in patient_record
    assert "07700 900123" in patient_record and "https://wa.me/447700900123" in patient_record
    assert ">CPF<" not in patient_record and ">RG<" not in patient_record


def test_patient_in_brazil_keeps_cpf_and_cities(clinic_a, create_user, client_for):
    admin = client_for(create_user("admin_brasil", clinic_a, Role.ADMIN))
    form_page = admin.get(reverse("patients:new")).content.decode()
    assert 'name="tax_id"' in form_page and 'name="state"' in form_page
    assert 'name="city_name"' not in form_page and ">CEP" in form_page


def test_schedule_shows_clinic_time_whatever_the_browser(
    clinic_a, create_user, create_practitioner, client_for
):
    """The calendar runs in UTC mode with the clinic's wall clock: an appointment at 09:00 in
    London comes as 09:00 without an offset, and the range it asks for (with "Z") is read in the
    clinic's time zone, so a browser in another zone shows the same times as the rest."""
    import zoneinfo

    from apps.schedule.models import Appointment, AppointmentType

    in_country(clinic_a, "GB")
    ana = create_practitioner(clinic_a, "Dr. Fictício de Londres")
    london = zoneinfo.ZoneInfo("Europe/London")
    with use_clinic(clinic_a):
        Appointment.objects.create(
            practitioner=ana,
            kind=AppointmentType.objects.first(),
            description="Horário fictício",
            start=datetime.datetime(2031, 3, 3, 9, 0, tzinfo=london),
            end=datetime.datetime(2031, 3, 3, 9, 30, tzinfo=london),
        )
    user_client = client_for(create_user("recepcao_agenda_londres", clinic_a, Role.FRONT_DESK))
    event_list = user_client.get(
        reverse("schedule:events"),
        {"practitioner": ana.pk, "start": "2031-03-03T00:00:00Z", "end": "2031-03-04T00:00:00Z"},
    ).json()
    assert [(e["start"], e["end"]) for e in event_list] == [
        ("2031-03-03T09:00:00", "2031-03-03T09:30:00")
    ]


# --- Latin America (decision 120) -------------------------------------------------


@pytest.mark.parametrize(
    ("country", "typed", "kept", "shown", "whatsapp"),
    [
        ("MX", "55 1234 5678", "5512345678", "55 1234 5678", "https://wa.me/525512345678"),
        ("MX", "+52 1 55 1234 5678", "5512345678", "55 1234 5678", "https://wa.me/525512345678"),
        ("MX", "(664) 123 4567", "6641234567", "664 123 4567", "https://wa.me/526641234567"),
        ("AR", "011 15 1234-5678", "1112345678", "011 1234-5678", "https://wa.me/5491112345678"),
        ("AR", "+54 9 11 1234 5678", "1112345678", "011 1234-5678", "https://wa.me/5491112345678"),
        ("AR", "0351 15 123-4567", "3511234567", "0351 123-4567", "https://wa.me/5493511234567"),
        ("CL", "+56 9 1234 5678", "912345678", "9 1234 5678", "https://wa.me/56912345678"),
        ("CO", "300 123 4567", "3001234567", "300 123 4567", "https://wa.me/573001234567"),
        ("CO", "601 234 5678", "6012345678", "601 234 5678", "https://wa.me/576012345678"),
        ("PE", "987 654 321", "987654321", "987 654 321", "https://wa.me/51987654321"),
        ("PE", "(01) 234 5678", "12345678", "(01) 234 5678", "https://wa.me/5112345678"),
        ("UY", "099 123 456", "99123456", "099 123 456", "https://wa.me/59899123456"),
        ("UY", "2123 4567", "21234567", "2123 4567", "https://wa.me/59821234567"),
        ("PY", "0981 123 456", "981123456", "0981 123 456", "https://wa.me/595981123456"),
        ("BO", "7123 4567", "71234567", "7123 4567", "https://wa.me/59171234567"),
        ("EC", "099 123 4567", "991234567", "099 123 4567", "https://wa.me/593991234567"),
        ("EC", "(02) 234 5678", "22345678", "(02) 234 5678", "https://wa.me/59322345678"),
    ],
)
def test_latin_american_phone(country, typed, kept, shown, whatsapp):
    assert normalize_phone(typed, country) == kept
    assert countries.format_phone(kept, country) == shown
    assert countries.whatsapp_link(kept, country) == whatsapp


@pytest.mark.parametrize(
    ("country", "typed"),
    [("MX", "1234 5678"), ("AR", "011 1234"), ("CL", "1234 5678"), ("UY", "099 123")],
)
def test_invalid_latin_american_phone(country, typed):
    with pytest.raises(ValidationError):
        normalize_phone(typed, country)


@pytest.mark.parametrize(
    ("country", "typed", "kept"),
    [
        ("MX", "06600", "06600"),
        ("AR", "c1425abc", "C1425ABC"),
        ("AR", "1425", "1425"),
        ("CL", "8320000", "8320000"),
        ("CO", "110111", "110111"),
        ("PE", "15001", "15001"),
        ("UY", "11000", "11000"),
        ("PY", "001001", "001001"),
        ("BO", "zona sur", "ZONASUR"),
        ("EC", "170150", "170150"),
    ],
)
def test_latin_american_postal_code(country, typed, kept):
    assert countries.normalize_postal_code(typed, country) == kept


@pytest.mark.parametrize(("country", "typed"), [("MX", "0660"), ("CL", "83200"), ("AR", "C14ABC")])
def test_invalid_latin_american_postal_code(country, typed):
    with pytest.raises(ValidationError):
        countries.normalize_postal_code(typed, country)


@pytest.mark.parametrize(
    ("country", "variant", "value"),
    [
        ("MX", "es-mx", "$ 1,234.56"),
        ("AR", "es-ar", "$ 1.234,56"),
        ("CL", "es-cl", "$ 1.235"),
        ("CO", "es-co", "$ 1.234,56"),
        ("PE", "es-pe", "S/ 1,234.56"),
        ("UY", "es-uy", "$U 1.234,56"),
        ("PY", "es-py", "₲ 1.235"),
        ("BO", "es-bo", "Bs 1.234,56"),
        ("EC", "es-ec", "US$ 1.234,56"),
    ],
)
def test_spanish_of_each_country(country, variant, value, clinic_a, create_user):
    """Spanish with each country's numbers and its currency, texts from the es catalog."""
    from apps.core import currencies

    user = create_user(f"recepcao_{country.lower()}", clinic_a, Role.FRONT_DESK)
    in_country(clinic_a, country)
    with translation.override("es"):
        assert _during_request(user)["language"] == variant
    with translation.override(variant):
        assert (
            currencies.format_amount(Decimal("1234.56"), countries.COUNTRIES[country].currency)
            == value
        )
        assert translation.gettext("Rechamadas") == "Recordatorios"


def test_latin_country_in_form_sets_time_zone_and_currency(clinic_a, create_user, client_for):
    admin = client_for(create_user("admin_mexico", clinic_a, Role.ADMIN))
    assert admin.post(reverse("clinic_settings"), clinic_data(country="MX")).status_code == 302
    clinic_a.refresh_from_db()
    assert (clinic_a.time_zone, clinic_a.currency) == ("America/Mexico_City", "MXN")
    # The screen sends the currency it shows (the clinic's, now the Mexican peso).
    data = clinic_data(country="AR", currency="MXN", time_zone="America/Argentina/Mendoza")
    assert admin.post(reverse("clinic_settings"), data).status_code == 302
    clinic_a.refresh_from_db()
    assert (clinic_a.time_zone, clinic_a.currency) == ("America/Argentina/Mendoza", "ARS")
