"""Each country's documents (decision 121): patients, the clinic, staff, suppliers and the
practitioners' registration. Brazil keeps its CPF/CNPJ rules (the other test files). Numbers
are the published examples of each document, not real people's."""

import pytest
from django.template import Context, Template
from django.urls import reverse

from apps.core import countries, identification
from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.finance.models import Supplier
from apps.patients.models import Patient
from apps.staff.models import Employee
from tests.test_core import dados_clinica
from tests.test_countries import no_pais

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_documentos", clinica_a, Role.ADMIN))


# --- The table of documents ------------------------------------------------------


def test_every_country_has_its_documents():
    assert identification.DOCUMENTS.keys() == countries.COUNTRIES.keys()
    for code, documentos in identification.DOCUMENTS.items():
        # Every country identifies a company (a company patient, the clinic, a supplier).
        assert documentos.empresa is not None, code
        assert documentos.registro_profissional, code


def test_field_examples_are_valid_and_written_as_the_system_writes():
    for code, documentos in identification.DOCUMENTS.items():
        if code == "BR":
            continue  # Brazil shows the mask, 000.000.000-00
        for document in documentos.of_roles(*identification.DOCUMENT_ROLES):
            compacto = document.normalize(document.example)
            assert document.is_valid(compacto), (code, document.abbreviation)
            assert document.write(compacto) in (document.example, compacto), document.abbreviation


@pytest.mark.parametrize(
    ("country", "role", "digitado", "escrito"),
    [
        ("MX", "paciente", "boxw310820hnerxn09", "BOXW310820HNERXN09"),
        ("MX", "pessoa", "GODE-561231-GR8", "GODE561231GR8"),
        ("MX", "empresa", "ABC 680524 P76", "ABC680524P76"),
        ("AR", "paciente", "20.123.456", "20.123.456"),
        ("AR", "empresa", "20123456786", "20-12345678-6"),
        ("CL", "paciente", "12345678-5", "12.345.678-5"),
        ("CO", "paciente", "1234567890", "1.234.567.890"),
        ("CO", "empresa", "2131234321", "213.123.432-1"),
        ("PE", "paciente", "12345678", "12345678"),
        ("PE", "empresa", "20512333797", "20512333797"),
        ("UY", "paciente", "1234567-2", "1.234.567-2"),
        ("UY", "empresa", "211003420017", "21-100342-001-7"),
        ("PY", "paciente", "1234567", "1.234.567"),
        ("PY", "empresa", "800280610", "80028061-0"),
        ("BO", "paciente", "1234567 lp", "1234567LP"),
        ("EC", "paciente", "1710034065", "1710034065"),
        ("EC", "empresa", "1792060346-001", "1792060346001"),
        ("US", "funcionario", "536904399", "536-90-4399"),
        ("US", "empresa", "911144442", "91-1144442"),
        ("GB", "paciente", "9434765919", "943 476 5919"),
        ("GB", "funcionario", "ab123456c", "AB 12 34 56 C"),
        ("GB", "empresa", "SC123456", "SC123456"),
        ("CA", "funcionario", "123 456 782", "123-456-782"),
        ("CA", "empresa", "123456782rt0001", "123456782 RT0001"),
        ("AU", "paciente", "2123456701", "2123 45670 1"),
        ("AU", "empresa", "83914571673", "83 914 571 673"),
        ("ZA", "paciente", "7503305044089", "7503305044089"),
        ("ZA", "empresa", "2001/123456/07", "2001/123456/07"),
    ],
)
def test_valid_document_is_written_the_country_way(country, role, digitado, escrito):
    document = identification.for_country(country).for_role(role)
    guardado = identification.clean_value(digitado, [document], document.abbreviation)
    assert identification.write(guardado, (role,), country) == escrito


@pytest.mark.parametrize(
    ("country", "role", "digitado"),
    [
        ("MX", "paciente", "BOXW310820HNERXN08"),  # check digit
        ("MX", "empresa", "GODE561231GR8"),  # an individual's RFC is not a company's
        ("AR", "empresa", "20123456785"),
        ("CL", "paciente", "12345678-K"),
        ("CO", "empresa", "2131234325"),
        ("UY", "paciente", "1234567-3"),
        ("EC", "paciente", "1710034066"),
        ("US", "funcionario", "000-12-3456"),
        ("GB", "paciente", "9434765918"),
        ("GB", "funcionario", "QQ123456C"),  # Q never starts one
        ("CA", "funcionario", "123456789"),
        ("AU", "paciente", "2123456711"),
        ("AU", "empresa", "83914571674"),
        ("ZA", "paciente", "7503305044088"),
    ],
)
def test_invalid_document_is_refused(country, role, digitado):
    document = identification.for_country(country).for_role(role)
    with pytest.raises(identification.ValidationError, match="número inválido"):
        identification.clean_value(digitado, [document], document.abbreviation)


def test_value_that_is_not_a_country_document_stays_as_is():
    # A CPF kept from when the clinic was Brazilian, now in the United States.
    assert identification.write("52998224725", None, "US") == "52998224725"
    assert identification.abbreviation("52998224725", ("pessoa", "empresa"), "US") == "EIN"
    assert (
        identification.abbreviation("", ("paciente", "empresa"), "GB")
        == "NHS number/Company number"
    )


def test_template_filters(clinica_a):
    no_pais(clinica_a, "AR")
    template = Template(
        '{% load formats %}{{ a|document:"paciente" }} · {{ b|document }} · '
        '{{ b|document_abbreviation:"empresa" }} · {% document_label "paciente" "empresa" %}'
    )
    with use_clinic(clinica_a):
        text = template.render(Context({"a": "20123456", "b": "20123456786"}))
    assert text == "20.123.456 · 20-12345678-6 · CUIT · DNI/CUIT"


# --- Patients ----------------------------------------------------------------------


def test_patient_in_mexico_with_curp(clinica_a, admin):
    no_pais(clinica_a, "MX")
    formulario = admin.get(reverse("patients:new")).content.decode()
    assert 'data-label-pf="CURP"' in formulario and 'data-label-pj="RFC"' in formulario
    data = {"kind": "PF", "name": "Paciente Ficticio", "active": "on"}
    response = admin.post(reverse("patients:new"), {**data, "tax_id": "BOXW310820HNERXN08"})
    assert response.context["form"].errors["tax_id"] == ["CURP: número inválido."]
    response = admin.post(reverse("patients:new"), {**data, "tax_id": "boxw310820hnerxn09"})
    assert response.status_code == 302
    with use_clinic(clinica_a):
        paciente = Patient.objects.get()
    assert paciente.tax_id == "BOXW310820HNERXN09"
    patient_record = admin.get(reverse("patients:record", args=[paciente.pk])).content.decode()
    assert "CURP" in patient_record and "BOXW310820HNERXN09" in patient_record

    # The same document again is refused, as in Brazil.
    response = admin.post(reverse("patients:new"), {**data, "tax_id": "BOXW310820HNERXN09"})
    assert "Já existe um paciente com este documento" in response.content.decode()


def test_patient_in_united_states_only_company_has_document(clinica_a, admin):
    no_pais(clinica_a, "US")
    formulario = admin.get(reverse("patients:new")).content.decode()
    assert 'data-label-pf=""' in formulario and 'data-label-pj="EIN"' in formulario
    # An individual: whatever was left in the hidden field is not kept.
    pessoa = {"kind": "PF", "name": "John Fictitious", "active": "on", "tax_id": "911144442"}
    assert admin.post(reverse("patients:new"), pessoa).status_code == 302
    empresa = {"kind": "PJ", "name": "Acme Fictitious", "active": "on", "tax_id": "91-1144442"}
    assert admin.post(reverse("patients:new"), empresa).status_code == 302
    with use_clinic(clinica_a):
        assert Patient.objects.get(name="John Fictitious").tax_id == ""
        acme = Patient.objects.get(name="Acme Fictitious")
    assert acme.tax_id == "911144442"
    results = admin.get(reverse("patients:list")).content.decode()
    assert "91-1144442" in results and "<th>EIN</th>" in results


# --- The clinic --------------------------------------------------------------------


def test_clinic_document_is_the_chosen_country_one(clinica_a, admin):
    # The country and the document change together: the document is the new country's.
    response = admin.post(
        reverse("clinic_settings"), dados_clinica(country="US", document="52998224725")
    )
    assert response.context["form"].errors["document"] == ["EIN: número inválido."]
    response = admin.post(
        reverse("clinic_settings"), dados_clinica(country="US", document="911144442")
    )
    assert response.status_code == 302
    clinica_a.refresh_from_db()
    assert clinica_a.document == "911144442"
    assert (clinica_a.document_abbreviation, clinica_a.written_document) == ("EIN", "91-1144442")


def test_clinic_in_mexico_accepts_person_or_company_rfc(clinica_a, admin):
    for rfc in ("GODE561231GR8", "ABC680524P76"):
        response = admin.post(reverse("clinic_settings"), dados_clinica(country="MX", document=rfc))
        assert response.status_code == 302
        clinica_a.refresh_from_db()
        assert (clinica_a.document, clinica_a.document_abbreviation) == (rfc, "RFC")


# --- Suppliers, staff and practitioners --------------------------------------------


def test_supplier_in_the_united_kingdom(clinica_a, admin):
    no_pais(clinica_a, "GB")
    empresa = {"kind": "PJ", "name": "Dental Supplies Ltd", "active": "on", "tax_id": "123"}
    response = admin.post(reverse("finance:supplier_new"), empresa)
    assert response.context["form"].errors["tax_id"] == ["Company number: número inválido."]
    empresa["tax_id"] = "01234567"
    assert admin.post(reverse("finance:supplier_new"), empresa).status_code == 302
    # A sole trader has no document in this table: nothing is kept.
    pessoa = {"kind": "PF", "name": "John Plumber", "active": "on", "tax_id": "01234567"}
    assert admin.post(reverse("finance:supplier_new"), pessoa).status_code == 302
    with use_clinic(clinica_a):
        assert Supplier.objects.get(name="Dental Supplies Ltd").tax_id == "01234567"
        assert Supplier.objects.get(name="John Plumber").tax_id == ""


def test_employee_in_the_united_states_and_australia(clinica_a, admin):
    no_pais(clinica_a, "US")
    data = {"name": "Jane Fictitious", "salary": "3000", "active": "on"}
    response = admin.post(reverse("staff:new"), {**data, "tax_id": "000-12-3456"})
    assert response.context["form"].errors["tax_id"] == ["SSN: número inválido."]
    assert admin.post(reverse("staff:new"), {**data, "tax_id": "536904399"}).status_code == 302
    with use_clinic(clinica_a):
        jane = Employee.objects.get()
    assert jane.tax_id == "536904399"
    patient_record = admin.get(reverse("staff:employee", args=[jane.pk])).content.decode()
    assert "SSN" in patient_record and "536-90-4399" in patient_record

    # Australia: the tax file number is not recorded, so there is no field.
    no_pais(clinica_a, "AU")
    assert 'name="tax_id"' not in admin.get(reverse("staff:new")).content.decode()


def test_professional_registration_with_country_examples(clinica_a, admin):
    no_pais(clinica_a, "GB")
    assert "GDC, GMC" in admin.get(reverse("practitioners:new")).content.decode()
    no_pais(clinica_a, "BR")
    assert "CRO, CRM" in admin.get(reverse("practitioners:new")).content.decode()
