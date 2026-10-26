import datetime

import pytest
from django.template import Context, Template
from django.urls import reverse

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.core.validadores import cnpj_valido, cpf_valido
from apps.pacientes.models import Paciente
from apps.referencias.models import Cidade

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


def criar_paciente(clinica, **dados):
    with usar_clinica(clinica):
        return Paciente.objects.create(**{"nome": "Paciente", **dados})


def dados_formulario(**extra):
    return {"tipo": "PF", "nome": "Maria da Silva", "ativo": "on", **extra}


# --- Validators and formats ------------------------------------------------------


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (CPF, True),
        ("52998224725", True),
        ("529.982.247-24", False),
        ("111.111.111-11", False),
        ("123", False),
    ],
)
def test_validacao_de_cpf(valor, esperado):
    assert cpf_valido(valor) is esperado


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (CNPJ, True),
        ("11.222.333/0001-82", False),
        (CNPJ_ALFANUMERICO, True),
        ("12abc34501de35", True),
        ("12.ABC.345/01DE-36", False),
        ("00000000000000", False),
    ],
)
def test_validacao_de_cnpj_numerico_e_alfanumerico(valor, esperado):
    assert cnpj_valido(valor) is esperado


def test_filtros_de_formatacao():
    template = Template(
        "{% load formatos %}{{ a|cpf_cnpj }} {{ b|cpf_cnpj }} "
        "{{ c|telefone }} {{ d|telefone }} {{ e|cep }}"
    )
    contexto = Context(
        {
            "a": "52998224725",
            "b": "12ABC34501DE35",
            "c": "48999990000",
            "d": "4833330000",
            "e": "88010000",
        }
    )
    assert template.render(contexto) == (
        "529.982.247-25 12.ABC.345/01DE-35 (48) 99999-0000 (48) 3333-0000 88010-000"
    )


def test_idade(clinica_a):
    hoje = datetime.date.today()
    nascimento = hoje.replace(year=hoje.year - 30)
    assert criar_paciente(clinica_a, data_nascimento=nascimento).idade == 30
    amanha_ha_30_anos = nascimento + datetime.timedelta(days=1)
    assert criar_paciente(clinica_a, data_nascimento=amanha_ha_30_anos).idade == 29
    assert criar_paciente(clinica_a).idade is None


# --- Form ------------------------------------------------------------------------


def test_cadastro_normaliza_documentos_e_telefones(admin_a, clinica_a):
    resposta = admin_a.post(
        reverse("pacientes:novo"),
        dados_formulario(
            cpf_cnpj=CPF,
            telefone_celular="(48) 99999-0000",
            cep="88010-000",
            uf=SC,
            cidade=FLORIANOPOLIS,
        ),
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.get(nome="Maria da Silva")
    assert resposta.url == reverse("pacientes:ficha", args=[paciente.pk])
    assert paciente.cpf_cnpj == "52998224725"
    assert paciente.telefone_celular == "48999990000"
    assert paciente.cep == "88010000"
    assert paciente.cidade.nome == "Florianópolis"


def test_pessoa_juridica_com_cnpj_alfanumerico(admin_a, clinica_a):
    resposta = admin_a.post(
        reverse("pacientes:novo"),
        dados_formulario(
            tipo="PJ",
            nome="Empresa X",
            razao_social="Empresa X Ltda.",
            cpf_cnpj=CNPJ_ALFANUMERICO,
            rg="123",
            sexo="F",
        ),
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.get(nome="Empresa X")
    assert paciente.cpf_cnpj == "12ABC34501DE35"
    assert paciente.rg == "" and paciente.sexo == ""  # individual-only fields are cleared


@pytest.mark.parametrize(
    ("dados", "campo", "mensagem"),
    [
        ({"cpf_cnpj": "529.982.247-24"}, "cpf_cnpj", "CPF inválido"),
        ({"tipo": "PJ", "cpf_cnpj": CPF}, "cpf_cnpj", "CNPJ inválido"),
        ({"telefone_celular": "9999-0000"}, "telefone_celular", "Informe o DDD"),
        ({"cep": "123"}, "cep", "8 dígitos"),
        ({"data_nascimento": "2999-01-01"}, "data_nascimento", "futuro"),
        ({"nome": ""}, "nome", "obrigatório"),
    ],
)
def test_validacoes_do_formulario(admin_a, dados, campo, mensagem):
    resposta = admin_a.post(reverse("pacientes:novo"), dados_formulario(**dados))
    assert resposta.status_code == 200
    erros = resposta.context["form"].errors
    assert campo in erros
    assert mensagem in " ".join(erros[campo])


def test_cidade_precisa_ser_da_uf_escolhida(admin_a):
    sao_paulo = Cidade.objects.get(nome="São Paulo", uf__sigla="SP")
    resposta = admin_a.post(reverse("pacientes:novo"), dados_formulario(uf=SC, cidade=sao_paulo.pk))
    assert resposta.status_code == 200
    assert "cidade" in resposta.context["form"].errors


def test_cpf_repetido_na_mesma_clinica_e_recusado_mas_vale_em_outra(admin_a, clinica_a, clinica_b):
    criar_paciente(clinica_a, cpf_cnpj="52998224725")
    resposta = admin_a.post(reverse("pacientes:novo"), dados_formulario(cpf_cnpj=CPF))
    assert "Já existe um paciente com este CPF/CNPJ" in resposta.content.decode()
    criar_paciente(clinica_b, cpf_cnpj="52998224725")  # another clinic: allowed


def test_edicao_mantem_as_cidades_da_uf(admin_a, clinica_a):
    paciente = criar_paciente(clinica_a, uf_id=SC, cidade_id=FLORIANOPOLIS)
    conteudo = admin_a.get(reverse("pacientes:editar", args=[paciente.pk])).content.decode()
    assert f'<option value="{FLORIANOPOLIS}" selected>Florianópolis</option>' in conteudo


# --- List and search -------------------------------------------------------------


def test_busca_por_nome_sem_acento_codigo_e_cpf(admin_a, clinica_a):
    joao = criar_paciente(clinica_a, nome="João Conceição", cpf_cnpj="52998224725")
    criar_paciente(clinica_a, nome="Ana Souza", cpf_cnpj="11144477735")
    url = reverse("pacientes:lista")

    def nomes(**params):
        return [p.nome for p in admin_a.get(url, params).context["pagina"]]

    assert nomes(q="joao conceicao") == ["João Conceição"]
    assert nomes(q="529.982") == ["João Conceição"]
    assert nomes(q=str(joao.pk)) == ["João Conceição"]
    assert nomes() == ["Ana Souza", "João Conceição"]


def test_filtros_de_tipo_e_situacao(admin_a, clinica_a):
    criar_paciente(clinica_a, nome="Ativo PF")
    criar_paciente(clinica_a, nome="Inativo PF", ativo=False)
    criar_paciente(clinica_a, nome="Empresa", tipo="PJ")
    url = reverse("pacientes:lista")

    def nomes(**params):
        return sorted(p.nome for p in admin_a.get(url, params).context["pagina"])

    assert nomes() == ["Ativo PF", "Empresa"]
    assert nomes(situacao="inativos") == ["Inativo PF"]
    assert nomes(situacao="todos", tipo="PJ") == ["Empresa"]


# --- Isolation and permissions ---------------------------------------------------


@pytest.mark.parametrize("rota", ["pacientes:ficha", "pacientes:editar", "pacientes:excluir"])
def test_paciente_de_outra_clinica_da_404(rota, admin_a, clinica_b):
    de_b = criar_paciente(clinica_b, nome="Paciente da B")
    assert admin_a.get(reverse(rota, args=[de_b.pk])).status_code == 404
    assert admin_a.post(reverse(rota, args=[de_b.pk]), dados_formulario()).status_code == 404


def test_lista_e_busca_nao_mostram_outra_clinica(admin_a, clinica_b):
    criar_paciente(clinica_b, nome="Paciente da B", cpf_cnpj="52998224725")
    for busca in ["", "Paciente da B", "52998224725"]:
        pagina = admin_a.get(reverse("pacientes:lista"), {"q": busca}).context["pagina"]
        assert len(pagina) == 0


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_recepcao_e_profissional_cadastram_mas_nao_excluem(
    papel, clinica_a, criar_usuario, cliente_de
):
    paciente = criar_paciente(clinica_a, nome="Paciente")
    cliente = cliente_de(criar_usuario("usuario", clinica_a, papel))
    assert cliente.post(reverse("pacientes:novo"), dados_formulario()).status_code == 302
    assert cliente.get(reverse("pacientes:editar", args=[paciente.pk])).status_code == 200
    assert cliente.post(reverse("pacientes:excluir", args=[paciente.pk])).status_code == 403
    assert ">Excluir<" not in cliente.get(reverse("pacientes:lista")).content.decode()


def test_admin_exclui(admin_a, clinica_a):
    paciente = criar_paciente(clinica_a, nome="Paciente")
    resposta = admin_a.post(reverse("pacientes:excluir", args=[paciente.pk]))
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        assert not Paciente.objects.exists()


def test_ficha_mostra_dados_formatados(admin_a, clinica_a):
    paciente = criar_paciente(
        clinica_a,
        nome="Maria",
        cpf_cnpj="52998224725",
        telefone_celular="48999990000",
        cidade_id=FLORIANOPOLIS,
        uf_id=SC,
    )
    conteudo = admin_a.get(reverse("pacientes:ficha", args=[paciente.pk])).content.decode()
    assert "529.982.247-25" in conteudo
    assert "(48) 99999-0000" in conteudo
    assert "Florianópolis/SC" in conteudo
