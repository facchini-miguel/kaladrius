import datetime

import pytest
from django.template import Context, Template
from django.urls import reverse

from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.core.validators import cnpj_valido, cpf_valido
from apps.patients.models import Patient
from apps.reference_data.models import City

pytestmark = pytest.mark.django_db

CPF = "529.982.247-25"
CPF_2 = "111.444.777-35"
CNPJ = "11.222.333/0001-81"
CNPJ_ALFANUMERICO = "12.ABC.345/01DE-35"
FLORIANOPOLIS = 4205407
SC = 42


@pytest.fixture
def admin_a(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_a", clinica_a, Papel.ADMIN))


def criar_paciente(clinic, **data):
    with usar_clinica(clinic):
        return Patient.objects.create(**{"name": "Paciente", **data})


def dados_formulario(**extra):
    return {"kind": "PF", "name": "Maria da Silva", "active": "on", **extra}


# --- Validators and formats ------------------------------------------------------


@pytest.mark.parametrize(
    ("amount", "esperado"),
    [
        (CPF, True),
        ("52998224725", True),
        ("529.982.247-24", False),
        ("111.111.111-11", False),
        ("123", False),
    ],
)
def test_validacao_de_cpf(amount, esperado):
    assert cpf_valido(amount) is esperado


@pytest.mark.parametrize(
    ("amount", "esperado"),
    [
        (CNPJ, True),
        ("11.222.333/0001-82", False),
        (CNPJ_ALFANUMERICO, True),
        ("12abc34501de35", True),
        ("12.ABC.345/01DE-36", False),
        ("00000000000000", False),
    ],
)
def test_validacao_de_cnpj_numerico_e_alfanumerico(amount, esperado):
    assert cnpj_valido(amount) is esperado


def test_filtros_de_formatacao():
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


def test_idade(clinica_a):
    today = datetime.date.today()
    nascimento = today.replace(year=today.year - 30)
    assert criar_paciente(clinica_a, birth_date=nascimento).idade == 30
    amanha_ha_30_anos = nascimento + datetime.timedelta(days=1)
    assert criar_paciente(clinica_a, birth_date=amanha_ha_30_anos).idade == 29
    assert criar_paciente(clinica_a).idade is None


# --- Form ------------------------------------------------------------------------


def test_cadastro_normaliza_documentos_e_telefones(admin_a, clinica_a):
    response = admin_a.post(
        reverse("patients:new"),
        dados_formulario(
            tax_id=CPF,
            mobile_phone="(48) 99999-0000",
            postal_code="88010-000",
            state=SC,
            city=FLORIANOPOLIS,
        ),
    )
    assert response.status_code == 302
    with usar_clinica(clinica_a):
        patient = Patient.objects.get(name="Maria da Silva")
    assert response.url == reverse("patients:record", args=[patient.pk])
    assert patient.tax_id == "52998224725"
    assert patient.mobile_phone == "48999990000"
    assert patient.postal_code == "88010000"
    assert patient.city.name == "Florianópolis"


def test_pessoa_juridica_com_cnpj_alfanumerico(admin_a, clinica_a):
    response = admin_a.post(
        reverse("patients:new"),
        dados_formulario(
            kind="PJ",
            name="Empresa X",
            legal_name="Empresa X Ltda.",
            tax_id=CNPJ_ALFANUMERICO,
            rg="123",
            sex="F",
        ),
    )
    assert response.status_code == 302
    with usar_clinica(clinica_a):
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
def test_validacoes_do_formulario(admin_a, data, field, message):
    response = admin_a.post(reverse("patients:new"), dados_formulario(**data))
    assert response.status_code == 200
    erros = response.context["form"].errors
    assert field in erros
    assert message in " ".join(erros[field])


def test_cidade_precisa_ser_da_uf_escolhida(admin_a):
    sao_paulo = City.objects.get(name="São Paulo", state__abbreviation="SP")
    response = admin_a.post(reverse("patients:new"), dados_formulario(state=SC, city=sao_paulo.pk))
    assert response.status_code == 200
    assert "city" in response.context["form"].errors


def test_cpf_repetido_na_mesma_clinica_e_recusado_mas_vale_em_outra(admin_a, clinica_a, clinica_b):
    criar_paciente(clinica_a, tax_id="52998224725")
    response = admin_a.post(reverse("patients:new"), dados_formulario(tax_id=CPF))
    assert "Já existe um paciente com este documento" in response.content.decode()
    criar_paciente(clinica_b, tax_id="52998224725")  # another clinic: allowed


def test_edicao_mantem_as_cidades_da_uf(admin_a, clinica_a):
    patient = criar_paciente(clinica_a, state_id=SC, city_id=FLORIANOPOLIS)
    content = admin_a.get(reverse("patients:edit", args=[patient.pk])).content.decode()
    assert f'<option value="{FLORIANOPOLIS}" selected>Florianópolis</option>' in content


# --- List and search -------------------------------------------------------------


def test_busca_por_nome_sem_acento_codigo_e_cpf(admin_a, clinica_a):
    joao = criar_paciente(clinica_a, name="João Conceição", tax_id="52998224725")
    criar_paciente(clinica_a, name="Ana Souza", tax_id="11144477735")
    url = reverse("patients:list")

    def nomes(**params):
        return [p.name for p in admin_a.get(url, params).context["pagina"]]

    assert nomes(q="joao conceicao") == ["João Conceição"]
    assert nomes(q="529.982") == ["João Conceição"]
    assert nomes(q=str(joao.pk)) == ["João Conceição"]
    assert nomes() == ["Ana Souza", "João Conceição"]


def test_filtros_de_tipo_e_situacao(admin_a, clinica_a):
    criar_paciente(clinica_a, name="Ativo PF")
    criar_paciente(clinica_a, name="Inativo PF", active=False)
    criar_paciente(clinica_a, name="Empresa", kind="PJ")
    url = reverse("patients:list")

    def nomes(**params):
        return sorted(p.name for p in admin_a.get(url, params).context["pagina"])

    assert nomes() == ["Ativo PF", "Empresa"]
    assert nomes(status="inativos") == ["Inativo PF"]
    assert nomes(status="todos", kind="PJ") == ["Empresa"]


# --- Isolation and permissions ---------------------------------------------------


@pytest.mark.parametrize("rota", ["patients:record", "patients:edit", "patients:delete"])
def test_paciente_de_outra_clinica_da_404(rota, admin_a, clinica_b):
    de_b = criar_paciente(clinica_b, name="Paciente da B")
    assert admin_a.get(reverse(rota, args=[de_b.pk])).status_code == 404
    assert admin_a.post(reverse(rota, args=[de_b.pk]), dados_formulario()).status_code == 404


def test_lista_e_busca_nao_mostram_outra_clinica(admin_a, clinica_b):
    criar_paciente(clinica_b, name="Paciente da B", tax_id="52998224725")
    for search in ["", "Paciente da B", "52998224725"]:
        page = admin_a.get(reverse("patients:list"), {"q": search}).context["pagina"]
        assert len(page) == 0


@pytest.mark.parametrize("role", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_recepcao_e_profissional_cadastram_mas_nao_excluem(
    role, clinica_a, criar_usuario, cliente_de
):
    patient = criar_paciente(clinica_a, name="Paciente")
    cliente = cliente_de(criar_usuario("usuario", clinica_a, role))
    assert cliente.post(reverse("patients:new"), dados_formulario()).status_code == 302
    assert cliente.get(reverse("patients:edit", args=[patient.pk])).status_code == 200
    assert cliente.post(reverse("patients:archive", args=[patient.pk])).status_code == 403
    assert cliente.post(reverse("patients:delete", args=[patient.pk])).status_code == 403
    assert ">Arquivar<" not in cliente.get(reverse("patients:list")).content.decode()


def test_admin_arquiva_e_restaura(admin_a, clinica_a, criar_usuario, cliente_de):
    patient = criar_paciente(clinica_a, name="Paciente Arquivável")
    # Not archived yet: permanent deletion is not available.
    assert admin_a.post(reverse("patients:delete", args=[patient.pk])).status_code == 404
    assert admin_a.post(reverse("patients:archive", args=[patient.pk])).status_code == 302
    patient.refresh_from_db()
    assert patient.archived and patient.archived_by.username == "admin_a"

    results = reverse("patients:list")
    for status, esperado in (("todos", []), ("arquivados", [patient])):
        assert list(admin_a.get(results, {"status": status}).context["pagina"]) == esperado
    ficha = admin_a.get(reverse("patients:record", args=[patient.pk])).content.decode()
    assert "Restaurar" in ficha and "Excluir definitivamente" in ficha
    assert admin_a.get(reverse("patients:edit", args=[patient.pk])).status_code == 404

    admin_a.post(reverse("patients:restore", args=[patient.pk]))
    patient.refresh_from_db()
    assert not patient.archived and patient.archived_by is None


def test_equipe_nao_ve_paciente_arquivado(clinica_a, criar_usuario, cliente_de):
    patient = criar_paciente(
        clinica_a, name="Fulano Escondido", tax_id="52998224725", archived=True
    )
    cliente = cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO))
    results = reverse("patients:list")
    for status in ("ativos", "todos", "arquivados"):
        assert "Escondido" not in cliente.get(results, {"status": status}).content.decode()
    assert cliente.get(reverse("patients:record", args=[patient.pk])).status_code == 404
    # The same CPF cannot be registered again: the message points to the administrator.
    response = cliente.post(reverse("patients:new"), dados_formulario(tax_id="529.982.247-25"))
    assert "paciente arquivado" in response.content.decode()


def test_ficha_mostra_dados_formatados(admin_a, clinica_a):
    patient = criar_paciente(
        clinica_a,
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
def test_busca_com_digitos_nao_ascii_nao_quebra(admin_a, clinica_a, search):
    criar_paciente(clinica_a, name="Maria")
    assert admin_a.get(reverse("patients:list"), {"q": search}).status_code == 200
    assert admin_a.get(reverse("patients:birthdays"), {"mes": search}).status_code == 200
    assert admin_a.get(reverse("reference_data:city_options"), {"state": search}).status_code == 200


def test_nao_arquiva_com_conta_em_aberto(admin_a, clinica_a, django_user_model):
    # Decision 075: the administrator first receives or cancels the open entries.
    from decimal import Decimal

    from apps.finance import services
    from apps.finance.models import Category, Entry, FinancialAccount

    patient = criar_paciente(clinica_a, name="Paciente Devedor")
    user = django_user_model.objects.get(username="admin_a")
    with usar_clinica(clinica_a):
        entry = services.criar_lancamento(
            clinic=clinica_a,
            kind=Entry.Tipo.RECEBER,
            description="Tratamento",
            category=Category.objects.get(name="Tratamento"),
            total_amount=Decimal("300"),
            parcelas=2,
            primeiro_vencimento=datetime.date(2031, 3, 5),
            user=user,
            patient=patient,
        )
    url = reverse("patients:archive", args=[patient.pk])
    page = admin_a.get(url)
    assert [p.number for p in page.context["abertas"]] == [1, 2]
    content = page.content.decode()
    assert reverse("finance:entry", args=[entry.pk]) in content
    assert 'btn btn-secondary">Arquivar<' not in content
    response = admin_a.post(url, follow=True)
    assert "Resolva as contas em aberto" in response.content.decode()
    patient.refresh_from_db()
    assert not patient.archived

    def receber(installment):
        with usar_clinica(clinica_a):
            services.receber(
                installment,
                user=user,
                amount=Decimal("150"),
                date=datetime.date(2031, 3, 5),
                method="pix",
                account=FinancialAccount.objects.get(name="Caixa"),
            )

    with usar_clinica(clinica_a):
        primeira, segunda = entry.parcelas.order_by("number")
    receber(primeira)
    assert [p.number for p in admin_a.get(url).context["abertas"]] == [2]
    receber(segunda)
    assert admin_a.post(url).status_code == 302
    patient.refresh_from_db()
    assert patient.archived
