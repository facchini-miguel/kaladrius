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
from apps.core.isolation import usar_clinica
from apps.core.middleware import ClinicaAtualMiddleware
from apps.core.models import Papel
from apps.core.validators import normalizar_telefone
from apps.patients.models import Patient
from tests.test_core import dados_clinica

pytestmark = pytest.mark.django_db


def no_pais(clinic, country, **extra):
    clinic.country = country
    clinic.time_zone = extra.pop("fuso", countries.PAISES[country].fusos[0])
    for campo, value in extra.items():
        setattr(clinic, campo, value)
    clinic.save()
    return clinic


# --- Phones ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("country", "digitado", "guardado", "exibido", "whatsapp"),
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
def test_telefone_de_cada_pais(country, digitado, guardado, exibido, whatsapp):
    assert normalizar_telefone(digitado, country) == guardado
    assert countries.formatar_telefone(guardado, country) == exibido
    assert countries.link_whatsapp(guardado, country) == whatsapp


@pytest.mark.parametrize(
    ("country", "digitado"),
    [("US", "555-0147"), ("US", "(112) 555-0147"), ("GB", "07700 900"), ("AU", "0612 345 678")],
)
def test_telefone_invalido_no_pais(country, digitado):
    with pytest.raises(ValidationError):
        normalizar_telefone(digitado, country)


def test_telefone_brasileiro_continua_igual(clinica_a):
    with usar_clinica(clinica_a):
        assert normalizar_telefone("(48) 8888-7777") == "48988887777"  # ninth digit added


# --- Postal codes ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("country", "digitado", "guardado", "exibido"),
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
def test_codigo_postal_de_cada_pais(country, digitado, guardado, exibido):
    assert countries.normalizar_cep(digitado, country) == guardado
    assert countries.formatar_cep(guardado, country) == exibido


@pytest.mark.parametrize(("country", "digitado"), [("US", "1000"), ("CA", "12345"), ("GB", "XYZ")])
def test_codigo_postal_invalido(country, digitado):
    with pytest.raises(ValidationError):
        countries.normalizar_cep(digitado, country)


# --- Time zone and the English variant -------------------------------------------


def _durante_requisicao(user):
    """Time zone and language active while a request of `usuario` runs."""
    visto = {}

    def resposta(request):
        visto["fuso"] = timezone.get_current_timezone_name()
        visto["language"] = translation.get_language()
        return HttpResponse()

    request = RequestFactory().get("/")
    request.user = user
    ClinicaAtualMiddleware(resposta)(request)
    return visto


def test_fuso_e_ingles_do_pais_durante_a_requisicao(clinica_a, criar_usuario):
    user = criar_usuario("recepcao_londres", clinica_a, Papel.RECEPCAO)
    no_pais(clinica_a, "GB")
    with translation.override("en"):
        assert _durante_requisicao(user) == {"fuso": "Europe/London", "language": "en-gb"}
    with translation.override("pt-br"):  # only English has country variants
        assert _durante_requisicao(user)["language"] == "pt-br"
    no_pais(clinica_a, "US", fuso="America/Chicago")
    with translation.override("en"):
        assert _durante_requisicao(user) == {"fuso": "America/Chicago", "language": "en"}
    assert timezone.get_current_timezone_name() == "America/Sao_Paulo"  # deactivated afterwards


def test_datas_em_ingles_britanico_e_bandeira_inglesa(clinica_a, criar_usuario, cliente_de):
    no_pais(clinica_a, "GB")
    cliente = cliente_de(criar_usuario("admin_londres", clinica_a, Papel.ADMIN))
    cliente.post(reverse("change_language"), {"language": "en"})
    pagina = cliente.get(reverse("home")).content.decode()
    assert '<html lang="en-gb">' in pagina
    # The English flag, with or without the hash of the collected static files (CI).
    assert re.search(r"flags/en(\.[0-9a-f]+)?\.svg", pagina) and "Patients" in pagina
    with usar_clinica(clinica_a):
        patient = Patient.objects.create(
            name="Amelia Fictícia", birth_date=datetime.date(2000, 12, 25)
        )
    ficha = cliente.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "25/12/2000" in ficha and "12/25/2000" not in ficha
    no_pais(clinica_a, "US")
    assert (
        "12/25/2000" in cliente.get(reverse("patients:record", args=[patient.pk])).content.decode()
    )


# --- Clinic settings -------------------------------------------------------------


def test_trocar_o_pais_ajusta_fuso_e_moeda(clinica_a, criar_usuario, cliente_de):
    admin = cliente_de(criar_usuario("admin_pais", clinica_a, Papel.ADMIN))
    assert admin.post(reverse("clinic_settings"), dados_clinica(country="GB")).status_code == 302
    clinica_a.refresh_from_db()
    assert (clinica_a.country, clinica_a.time_zone, clinica_a.currency) == (
        "GB",
        "Europe/London",
        "GBP",
    )
    # The document is the new country's (decision 121).
    assert admin.get(reverse("clinic_settings")).context["form"]["document"].label == (
        "Company number"
    )

    # A currency chosen on purpose is kept when the country changes.
    dados = dados_clinica(country="AU", currency="USD", time_zone="Australia/Perth")
    assert admin.post(reverse("clinic_settings"), dados).status_code == 302
    clinica_a.refresh_from_db()
    assert (clinica_a.country, clinica_a.time_zone, clinica_a.currency) == (
        "AU",
        "Australia/Perth",
        "USD",
    )


def test_fuso_de_outro_pais_e_recusado(clinica_a, criar_usuario, cliente_de):
    admin = cliente_de(criar_usuario("admin_fuso", clinica_a, Papel.ADMIN))
    resposta = admin.post(
        reverse("clinic_settings"), dados_clinica(country="ZA", time_zone="America/New_York")
    )
    assert resposta.status_code == 200 and "time_zone" in resposta.context["form"].errors


# --- Patients outside Brazil -----------------------------------------------------


def test_paciente_fora_do_brasil(clinica_a, criar_usuario, cliente_de):
    no_pais(clinica_a, "GB")
    admin = cliente_de(criar_usuario("admin_paciente", clinica_a, Papel.ADMIN))
    formulario = admin.get(reverse("patients:new")).content.decode()
    assert 'data-rotulo-pf="NHS number"' in formulario and 'name="rg"' not in formulario
    assert 'name="state"' not in formulario and 'name="city_name"' in formulario
    assert "Código postal" in formulario

    resposta = admin.post(
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
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        patient = Patient.objects.get(name="Oliver Fictício")
    assert (patient.mobile_phone, patient.whatsapp, patient.postal_code) == (
        "7700900123",
        "7700900123",
        "SW1A1AA",
    )
    ficha = admin.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "London, England" in ficha and "SW1A 1AA" in ficha
    assert "07700 900123" in ficha and "https://wa.me/447700900123" in ficha
    assert ">CPF<" not in ficha and ">RG<" not in ficha


def test_paciente_no_brasil_continua_com_cpf_e_cidades(clinica_a, criar_usuario, cliente_de):
    admin = cliente_de(criar_usuario("admin_brasil", clinica_a, Papel.ADMIN))
    formulario = admin.get(reverse("patients:new")).content.decode()
    assert 'name="tax_id"' in formulario and 'name="state"' in formulario
    assert 'name="city_name"' not in formulario and ">CEP" in formulario


def test_agenda_mostra_a_hora_da_clinica_seja_qual_for_o_navegador(
    clinica_a, criar_usuario, criar_profissional, cliente_de
):
    """The calendar runs in UTC mode with the clinic's wall clock: an appointment at 09:00 in
    London comes as 09:00 without an offset, and the range it asks for (with "Z") is read in the
    clinic's time zone, so a browser in another zone shows the same times as the rest."""
    import zoneinfo

    from apps.schedule.models import Appointment, AppointmentType

    no_pais(clinica_a, "GB")
    ana = criar_profissional(clinica_a, "Dr. Fictício de Londres")
    londres = zoneinfo.ZoneInfo("Europe/London")
    with usar_clinica(clinica_a):
        Appointment.objects.create(
            practitioner=ana,
            kind=AppointmentType.objects.first(),
            description="Horário fictício",
            start=datetime.datetime(2031, 3, 3, 9, 0, tzinfo=londres),
            end=datetime.datetime(2031, 3, 3, 9, 30, tzinfo=londres),
        )
    cliente = cliente_de(criar_usuario("recepcao_agenda_londres", clinica_a, Papel.RECEPCAO))
    eventos = cliente.get(
        reverse("schedule:events"),
        {"practitioner": ana.pk, "start": "2031-03-03T00:00:00Z", "end": "2031-03-04T00:00:00Z"},
    ).json()
    assert [(e["start"], e["end"]) for e in eventos] == [
        ("2031-03-03T09:00:00", "2031-03-03T09:30:00")
    ]


# --- Latin America (decision 120) -------------------------------------------------


@pytest.mark.parametrize(
    ("country", "digitado", "guardado", "exibido", "whatsapp"),
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
def test_telefone_da_america_latina(country, digitado, guardado, exibido, whatsapp):
    assert normalizar_telefone(digitado, country) == guardado
    assert countries.formatar_telefone(guardado, country) == exibido
    assert countries.link_whatsapp(guardado, country) == whatsapp


@pytest.mark.parametrize(
    ("country", "digitado"),
    [("MX", "1234 5678"), ("AR", "011 1234"), ("CL", "1234 5678"), ("UY", "099 123")],
)
def test_telefone_latino_invalido(country, digitado):
    with pytest.raises(ValidationError):
        normalizar_telefone(digitado, country)


@pytest.mark.parametrize(
    ("country", "digitado", "guardado"),
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
def test_codigo_postal_da_america_latina(country, digitado, guardado):
    assert countries.normalizar_cep(digitado, country) == guardado


@pytest.mark.parametrize(
    ("country", "digitado"), [("MX", "0660"), ("CL", "83200"), ("AR", "C14ABC")]
)
def test_codigo_postal_latino_invalido(country, digitado):
    with pytest.raises(ValidationError):
        countries.normalizar_cep(digitado, country)


@pytest.mark.parametrize(
    ("country", "variante", "value"),
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
def test_espanhol_de_cada_pais(country, variante, value, clinica_a, criar_usuario):
    """Spanish with each country's numbers and its currency, texts from the es catalog."""
    from apps.core import currencies

    user = criar_usuario(f"recepcao_{country.lower()}", clinica_a, Papel.RECEPCAO)
    no_pais(clinica_a, country)
    with translation.override("es"):
        assert _durante_requisicao(user)["language"] == variante
    with translation.override(variante):
        assert currencies.formatar(Decimal("1234.56"), countries.PAISES[country].currency) == value
        assert translation.gettext("Rechamadas") == "Recordatorios"


def test_pais_latino_no_formulario_ajusta_fuso_e_moeda(clinica_a, criar_usuario, cliente_de):
    admin = cliente_de(criar_usuario("admin_mexico", clinica_a, Papel.ADMIN))
    assert admin.post(reverse("clinic_settings"), dados_clinica(country="MX")).status_code == 302
    clinica_a.refresh_from_db()
    assert (clinica_a.time_zone, clinica_a.currency) == ("America/Mexico_City", "MXN")
    # The screen sends the currency it shows (the clinic's, now the Mexican peso).
    dados = dados_clinica(country="AR", currency="MXN", time_zone="America/Argentina/Mendoza")
    assert admin.post(reverse("clinic_settings"), dados).status_code == 302
    clinica_a.refresh_from_db()
    assert (clinica_a.time_zone, clinica_a.currency) == ("America/Argentina/Mendoza", "ARS")
