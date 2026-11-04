"""Each country's documents (decision 121): patients, the clinic, staff, suppliers and the
practitioners' registration. Brazil keeps its CPF/CNPJ rules (the other test files). Numbers
are the published examples of each document, not real people's."""

import pytest
from django.template import Context, Template
from django.urls import reverse

from apps.core import countries, identification
from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.finance.models import Supplier
from apps.patients.models import Patient
from apps.staff.models import Employee
from tests.test_core import dados_clinica
from tests.test_countries import no_pais

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_documentos", clinica_a, Papel.ADMIN))


# --- The table of documents ------------------------------------------------------


def test_todo_pais_tem_seus_documentos():
    assert identification.DOCUMENTOS.keys() == countries.PAISES.keys()
    for codigo, documentos in identification.DOCUMENTOS.items():
        # Every country identifies a company (a company patient, the clinic, a supplier).
        assert documentos.empresa is not None, codigo
        assert documentos.registro_profissional, codigo


def test_os_exemplos_dos_campos_sao_validos_e_escritos_como_o_sistema_escreve():
    for codigo, documentos in identification.DOCUMENTOS.items():
        if codigo == "BR":
            continue  # Brazil shows the mask, 000.000.000-00
        for documento in documentos.de(*identification.PAPEIS):
            compacto = documento.normalizar(documento.exemplo)
            assert documento.valido(compacto), (codigo, documento.sigla)
            assert documento.escrever(compacto) in (documento.exemplo, compacto), documento.sigla


@pytest.mark.parametrize(
    ("pais", "papel", "digitado", "escrito"),
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
def test_documento_valido_e_escrito_do_jeito_do_pais(pais, papel, digitado, escrito):
    documento = identification.do_pais(pais).do_papel(papel)
    guardado = identification.limpar(digitado, [documento], documento.sigla)
    assert identification.escrever(guardado, (papel,), pais) == escrito


@pytest.mark.parametrize(
    ("pais", "papel", "digitado"),
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
def test_documento_invalido_e_recusado(pais, papel, digitado):
    documento = identification.do_pais(pais).do_papel(papel)
    with pytest.raises(identification.ValidationError, match="número inválido"):
        identification.limpar(digitado, [documento], documento.sigla)


def test_valor_que_nao_e_documento_do_pais_fica_como_esta():
    # A CPF kept from when the clinic was Brazilian, now in the United States.
    assert identification.escrever("52998224725", None, "US") == "52998224725"
    assert identification.sigla("52998224725", ("pessoa", "empresa"), "US") == "EIN"
    assert identification.sigla("", ("paciente", "empresa"), "GB") == "NHS number/Company number"


def test_filtros_dos_templates(clinica_a):
    no_pais(clinica_a, "AR")
    template = Template(
        '{% load formats %}{{ a|documento:"paciente" }} · {{ b|documento }} · '
        '{{ b|sigla_documento:"empresa" }} · {% rotulo_documento "paciente" "empresa" %}'
    )
    with usar_clinica(clinica_a):
        texto = template.render(Context({"a": "20123456", "b": "20123456786"}))
    assert texto == "20.123.456 · 20-12345678-6 · CUIT · DNI/CUIT"


# --- Patients ----------------------------------------------------------------------


def test_paciente_no_mexico_com_curp(clinica_a, admin):
    no_pais(clinica_a, "MX")
    formulario = admin.get(reverse("patients:new")).content.decode()
    assert 'data-rotulo-pf="CURP"' in formulario and 'data-rotulo-pj="RFC"' in formulario
    dados = {"tipo": "PF", "nome": "Paciente Ficticio", "ativo": "on"}
    resposta = admin.post(reverse("patients:new"), {**dados, "cpf_cnpj": "BOXW310820HNERXN08"})
    assert resposta.context["form"].errors["cpf_cnpj"] == ["CURP: número inválido."]
    resposta = admin.post(reverse("patients:new"), {**dados, "cpf_cnpj": "boxw310820hnerxn09"})
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        paciente = Patient.objects.get()
    assert paciente.cpf_cnpj == "BOXW310820HNERXN09"
    ficha = admin.get(reverse("patients:record", args=[paciente.pk])).content.decode()
    assert "CURP" in ficha and "BOXW310820HNERXN09" in ficha

    # The same document again is refused, as in Brazil.
    resposta = admin.post(reverse("patients:new"), {**dados, "cpf_cnpj": "BOXW310820HNERXN09"})
    assert "Já existe um paciente com este documento" in resposta.content.decode()


def test_paciente_nos_estados_unidos_so_a_empresa_tem_documento(clinica_a, admin):
    no_pais(clinica_a, "US")
    formulario = admin.get(reverse("patients:new")).content.decode()
    assert 'data-rotulo-pf=""' in formulario and 'data-rotulo-pj="EIN"' in formulario
    # An individual: whatever was left in the hidden field is not kept.
    pessoa = {"tipo": "PF", "nome": "John Fictitious", "ativo": "on", "cpf_cnpj": "911144442"}
    assert admin.post(reverse("patients:new"), pessoa).status_code == 302
    empresa = {"tipo": "PJ", "nome": "Acme Fictitious", "ativo": "on", "cpf_cnpj": "91-1144442"}
    assert admin.post(reverse("patients:new"), empresa).status_code == 302
    with usar_clinica(clinica_a):
        assert Patient.objects.get(nome="John Fictitious").cpf_cnpj == ""
        acme = Patient.objects.get(nome="Acme Fictitious")
    assert acme.cpf_cnpj == "911144442"
    lista = admin.get(reverse("patients:list")).content.decode()
    assert "91-1144442" in lista and "<th>EIN</th>" in lista


# --- The clinic --------------------------------------------------------------------


def test_documento_da_clinica_e_o_do_pais_escolhido(clinica_a, admin):
    # The country and the document change together: the document is the new country's.
    resposta = admin.post(
        reverse("clinic_settings"), dados_clinica(pais="US", documento="52998224725")
    )
    assert resposta.context["form"].errors["documento"] == ["EIN: número inválido."]
    resposta = admin.post(
        reverse("clinic_settings"), dados_clinica(pais="US", documento="911144442")
    )
    assert resposta.status_code == 302
    clinica_a.refresh_from_db()
    assert clinica_a.documento == "911144442"
    assert (clinica_a.sigla_documento, clinica_a.documento_escrito) == ("EIN", "91-1144442")


def test_clinica_no_mexico_aceita_rfc_de_pessoa_ou_de_empresa(clinica_a, admin):
    for rfc in ("GODE561231GR8", "ABC680524P76"):
        resposta = admin.post(reverse("clinic_settings"), dados_clinica(pais="MX", documento=rfc))
        assert resposta.status_code == 302
        clinica_a.refresh_from_db()
        assert (clinica_a.documento, clinica_a.sigla_documento) == (rfc, "RFC")


# --- Suppliers, staff and practitioners --------------------------------------------


def test_fornecedor_no_reino_unido(clinica_a, admin):
    no_pais(clinica_a, "GB")
    empresa = {"tipo": "PJ", "nome": "Dental Supplies Ltd", "ativo": "on", "cpf_cnpj": "123"}
    resposta = admin.post(reverse("finance:supplier_new"), empresa)
    assert resposta.context["form"].errors["cpf_cnpj"] == ["Company number: número inválido."]
    empresa["cpf_cnpj"] = "01234567"
    assert admin.post(reverse("finance:supplier_new"), empresa).status_code == 302
    # A sole trader has no document in this table: nothing is kept.
    pessoa = {"tipo": "PF", "nome": "John Plumber", "ativo": "on", "cpf_cnpj": "01234567"}
    assert admin.post(reverse("finance:supplier_new"), pessoa).status_code == 302
    with usar_clinica(clinica_a):
        assert Supplier.objects.get(nome="Dental Supplies Ltd").cpf_cnpj == "01234567"
        assert Supplier.objects.get(nome="John Plumber").cpf_cnpj == ""


def test_funcionario_nos_estados_unidos_e_na_australia(clinica_a, admin):
    no_pais(clinica_a, "US")
    dados = {"nome": "Jane Fictitious", "salario": "3000", "ativo": "on"}
    resposta = admin.post(reverse("staff:new"), {**dados, "cpf": "000-12-3456"})
    assert resposta.context["form"].errors["cpf"] == ["SSN: número inválido."]
    assert admin.post(reverse("staff:new"), {**dados, "cpf": "536904399"}).status_code == 302
    with usar_clinica(clinica_a):
        jane = Employee.objects.get()
    assert jane.cpf == "536904399"
    ficha = admin.get(reverse("staff:employee", args=[jane.pk])).content.decode()
    assert "SSN" in ficha and "536-90-4399" in ficha

    # Australia: the tax file number is not recorded, so there is no field.
    no_pais(clinica_a, "AU")
    assert 'name="cpf"' not in admin.get(reverse("staff:new")).content.decode()


def test_registro_profissional_com_exemplos_do_pais(clinica_a, admin):
    no_pais(clinica_a, "GB")
    assert "GDC, GMC" in admin.get(reverse("practitioners:new")).content.decode()
    no_pais(clinica_a, "BR")
    assert "CRO, CRM" in admin.get(reverse("practitioners:new")).content.decode()
