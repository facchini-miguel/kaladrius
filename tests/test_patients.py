import datetime

import pytest
from django.template import Context, Template
from django.urls import reverse

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.core.validators import valid_cnpj, valid_cpf
from apps.patients.models import Patient
from apps.reference_data.models import City

pytestmark = pytest.mark.django_db

CPF = "529.982.247-25"
CPF_2 = "111.444.777-35"
CNPJ = "11.222.333/0001-81"
CNPJ_ALPHANUMERIC = "12.ABC.345/01DE-35"
FLORIANOPOLIS = 4205407
SC = 42


@pytest.fixture
def admin_a(clinic_a, create_user, client_for):
    return client_for(create_user("admin_a", clinic_a, Role.ADMIN))


def create_patient(clinic, **data):
    with use_clinic(clinic):
        return Patient.objects.create(**{"name": "Paciente", **data})


def form_data(**extra):
    return {"kind": "PF", "name": "Maria da Silva", "active": "on", **extra}


# --- Validators and formats ------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (CPF, True),
        ("52998224725", True),
        ("529.982.247-24", False),
        ("111.111.111-11", False),
        ("123", False),
    ],
)
def test_cpf_validation(amount, expected):
    assert valid_cpf(amount) is expected


@pytest.mark.parametrize(
    ("amount", "expected"),
    [
        (CNPJ, True),
        ("11.222.333/0001-82", False),
        (CNPJ_ALPHANUMERIC, True),
        ("12abc34501de35", True),
        ("12.ABC.345/01DE-36", False),
        ("00000000000000", False),
    ],
)
def test_numeric_and_alphanumeric_cnpj_validation(amount, expected):
    assert valid_cnpj(amount) is expected


def test_formatting_filters():
    template = Template(
        "{% load formats %}{{ a|document }} {{ b|document }} "
        "{{ c|phone }} {{ d|phone }} {{ e|postal_code }}"
    )
    context = Context(
        {
            "a": "52998224725",
            "b": "12ABC34501DE35",
            "c": "48999990000",
            "d": "4833330000",
            "e": "88010000",
        }
    )
    assert template.render(context) == (
        "529.982.247-25 12.ABC.345/01DE-35 (48) 99999-0000 (48) 3333-0000 88010-000"
    )


def test_age(clinic_a):
    today = datetime.date.today()
    birth = today.replace(year=today.year - 30)
    assert create_patient(clinic_a, birth_date=birth).age == 30
    tomorrow_30_years_ago = birth + datetime.timedelta(days=1)
    assert create_patient(clinic_a, birth_date=tomorrow_30_years_ago).age == 29
    assert create_patient(clinic_a).age is None


# --- Form ------------------------------------------------------------------------


def test_registration_normalizes_documents_and_phones(admin_a, clinic_a):
    response = admin_a.post(
        reverse("patients:new"),
        form_data(
            tax_id=CPF,
            mobile_phone="(48) 99999-0000",
            postal_code="88010-000",
            state=SC,
            city=FLORIANOPOLIS,
        ),
    )
    assert response.status_code == 302
    with use_clinic(clinic_a):
        patient = Patient.objects.get(name="Maria da Silva")
    assert response.url == reverse("patients:record", args=[patient.pk])
    assert patient.tax_id == "52998224725"
    assert patient.mobile_phone == "48999990000"
    assert patient.postal_code == "88010000"
    assert patient.city.name == "Florianópolis"


def test_company_with_alphanumeric_cnpj(admin_a, clinic_a):
    response = admin_a.post(
        reverse("patients:new"),
        form_data(
            kind="PJ",
            name="Empresa X",
            legal_name="Empresa X Ltda.",
            tax_id=CNPJ_ALPHANUMERIC,
            rg="123",
            sex="F",
        ),
    )
    assert response.status_code == 302
    with use_clinic(clinic_a):
        patient = Patient.objects.get(name="Empresa X")
    assert patient.tax_id == "12ABC34501DE35"
    assert patient.rg == "" and patient.sex == ""  # individual-only fields are cleared


@pytest.mark.parametrize(
    ("data", "field", "message"),
    [
        ({"tax_id": "529.982.247-24"}, "tax_id", "CPF: número inválido"),
        ({"kind": "PJ", "tax_id": CPF}, "tax_id", "CNPJ: número inválido"),
        ({"mobile_phone": "9999-0000"}, "mobile_phone", "Informe o DDD"),
        ({"postal_code": "123"}, "postal_code", "8 dígitos"),
        ({"birth_date": "2999-01-01"}, "birth_date", "futuro"),
        ({"name": ""}, "name", "obrigatório"),
    ],
)
def test_form_validations(admin_a, data, field, message):
    response = admin_a.post(reverse("patients:new"), form_data(**data))
    assert response.status_code == 200
    errors = response.context["form"].errors
    assert field in errors
    assert message in " ".join(errors[field])


def test_city_must_belong_to_the_chosen_state(admin_a):
    sao_paulo = City.objects.get(name="São Paulo", state__abbreviation="SP")
    response = admin_a.post(reverse("patients:new"), form_data(state=SC, city=sao_paulo.pk))
    assert response.status_code == 200
    assert "city" in response.context["form"].errors


def test_duplicate_cpf_refused_in_same_clinic_but_allowed_in_another(admin_a, clinic_a, clinic_b):
    create_patient(clinic_a, tax_id="52998224725")
    response = admin_a.post(reverse("patients:new"), form_data(tax_id=CPF))
    assert "Já existe um paciente com este documento" in response.content.decode()
    create_patient(clinic_b, tax_id="52998224725")  # another clinic: allowed


def test_editing_keeps_the_state_cities(admin_a, clinic_a):
    patient = create_patient(clinic_a, state_id=SC, city_id=FLORIANOPOLIS)
    content = admin_a.get(reverse("patients:edit", args=[patient.pk])).content.decode()
    assert f'<option value="{FLORIANOPOLIS}" selected>Florianópolis</option>' in content


# --- List and search -------------------------------------------------------------


def test_search_by_unaccented_name_code_and_cpf(admin_a, clinic_a):
    joao = create_patient(clinic_a, name="João Conceição", tax_id="52998224725")
    create_patient(clinic_a, name="Ana Souza", tax_id="11144477735")
    url = reverse("patients:list")

    def names(**params):
        return [p.name for p in admin_a.get(url, params).context["page"]]

    assert names(q="joao conceicao") == ["João Conceição"]
    assert names(q="529.982") == ["João Conceição"]
    assert names(q=str(joao.pk)) == ["João Conceição"]
    assert names() == ["Ana Souza", "João Conceição"]


def test_kind_and_status_filters(admin_a, clinic_a):
    create_patient(clinic_a, name="Ativo PF")
    create_patient(clinic_a, name="Inativo PF", active=False)
    create_patient(clinic_a, name="Empresa", kind="PJ")
    url = reverse("patients:list")

    def names(**params):
        return sorted(p.name for p in admin_a.get(url, params).context["page"])

    assert names() == ["Ativo PF", "Empresa"]
    assert names(status="inativos") == ["Inativo PF"]
    assert names(status="todos", kind="PJ") == ["Empresa"]


# --- Isolation and permissions ---------------------------------------------------


@pytest.mark.parametrize("route", ["patients:record", "patients:edit", "patients:delete"])
def test_patient_of_another_clinic_gives_404(route, admin_a, clinic_b):
    of_b = create_patient(clinic_b, name="Paciente da B")
    assert admin_a.get(reverse(route, args=[of_b.pk])).status_code == 404
    assert admin_a.post(reverse(route, args=[of_b.pk]), form_data()).status_code == 404


def test_list_and_search_do_not_show_another_clinic(admin_a, clinic_b):
    create_patient(clinic_b, name="Paciente da B", tax_id="52998224725")
    for search in ["", "Paciente da B", "52998224725"]:
        page = admin_a.get(reverse("patients:list"), {"q": search}).context["page"]
        assert len(page) == 0


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.PRACTITIONER])
def test_reception_and_practitioner_register_but_do_not_delete(
    role, clinic_a, create_user, client_for
):
    patient = create_patient(clinic_a, name="Paciente")
    user_client = client_for(create_user("usuario", clinic_a, role))
    assert user_client.post(reverse("patients:new"), form_data()).status_code == 302
    assert user_client.get(reverse("patients:edit", args=[patient.pk])).status_code == 200
    assert user_client.post(reverse("patients:archive", args=[patient.pk])).status_code == 403
    assert user_client.post(reverse("patients:delete", args=[patient.pk])).status_code == 403
    assert ">Arquivar<" not in user_client.get(reverse("patients:list")).content.decode()


def test_admin_archives_and_restores(admin_a, clinic_a, create_user, client_for):
    patient = create_patient(clinic_a, name="Paciente Arquivável")
    # Not archived yet: permanent deletion is not available.
    assert admin_a.post(reverse("patients:delete", args=[patient.pk])).status_code == 404
    assert admin_a.post(reverse("patients:archive", args=[patient.pk])).status_code == 302
    patient.refresh_from_db()
    assert patient.archived and patient.archived_by.username == "admin_a"

    patient_list = reverse("patients:list")
    for status, expected in (("todos", []), ("arquivados", [patient])):
        assert list(admin_a.get(patient_list, {"status": status}).context["page"]) == expected
    patient_record = admin_a.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "Restaurar" in patient_record and "Excluir definitivamente" in patient_record
    assert admin_a.get(reverse("patients:edit", args=[patient.pk])).status_code == 404

    admin_a.post(reverse("patients:restore", args=[patient.pk]))
    patient.refresh_from_db()
    assert not patient.archived and patient.archived_by is None


def test_team_does_not_see_archived_patient(clinic_a, create_user, client_for):
    patient = create_patient(clinic_a, name="Fulano Escondido", tax_id="52998224725", archived=True)
    user_client = client_for(create_user("recepcao", clinic_a, Role.FRONT_DESK))
    patient_list = reverse("patients:list")
    for status in ("ativos", "todos", "arquivados"):
        assert "Escondido" not in user_client.get(patient_list, {"status": status}).content.decode()
    assert user_client.get(reverse("patients:record", args=[patient.pk])).status_code == 404
    # The same CPF cannot be registered again: the message points to the administrator.
    response = user_client.post(reverse("patients:new"), form_data(tax_id="529.982.247-25"))
    assert "paciente arquivado" in response.content.decode()


def test_record_shows_formatted_data(admin_a, clinic_a):
    patient = create_patient(
        clinic_a,
        name="Maria",
        tax_id="52998224725",
        mobile_phone="48999990000",
        city_id=FLORIANOPOLIS,
        state_id=SC,
    )
    content = admin_a.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "529.982.247-25" in content
    assert "(48) 99999-0000" in content
    assert "Florianópolis/SC" in content


@pytest.mark.parametrize("search", ["²", "¹²³", "١٢"])
def test_search_with_non_ascii_digits_does_not_break(admin_a, clinic_a, search):
    create_patient(clinic_a, name="Maria")
    assert admin_a.get(reverse("patients:list"), {"q": search}).status_code == 200
    assert admin_a.get(reverse("patients:birthdays"), {"month": search}).status_code == 200
    assert admin_a.get(reverse("reference_data:city_options"), {"state": search}).status_code == 200


def test_does_not_archive_with_open_bill(admin_a, clinic_a, django_user_model):
    # Decision 075: the administrator first receives or cancels the open entries.
    from decimal import Decimal

    from apps.finance import services
    from apps.finance.models import Category, Entry, FinancialAccount

    patient = create_patient(clinic_a, name="Paciente Devedor")
    user = django_user_model.objects.get(username="admin_a")
    with use_clinic(clinic_a):
        entry = services.create_entry(
            clinic=clinic_a,
            kind=Entry.Kind.RECEIVABLE,
            description="Tratamento",
            category=Category.objects.get(name="Tratamento"),
            total_amount=Decimal("300"),
            installments=2,
            first_due_date=datetime.date(2031, 3, 5),
            user=user,
            patient=patient,
        )
    url = reverse("patients:archive", args=[patient.pk])
    page = admin_a.get(url)
    assert [p.number for p in page.context["open_items"]] == [1, 2]
    content = page.content.decode()
    assert reverse("finance:entry", args=[entry.pk]) in content
    assert 'btn btn-secondary">Arquivar<' not in content
    response = admin_a.post(url, follow=True)
    assert "Resolva as contas em aberto" in response.content.decode()
    patient.refresh_from_db()
    assert not patient.archived

    def receive_(installment):
        with use_clinic(clinic_a):
            services.receive(
                installment,
                user=user,
                amount=Decimal("150"),
                date=datetime.date(2031, 3, 5),
                method="pix",
                account=FinancialAccount.objects.get(name="Caixa"),
            )

    with use_clinic(clinic_a):
        first_one, second = entry.installments.order_by("number")
    receive_(first_one)
    assert [p.number for p in admin_a.get(url).context["open_items"]] == [2]
    receive_(second)
    assert admin_a.post(url).status_code == 302
    patient.refresh_from_db()
    assert patient.archived
