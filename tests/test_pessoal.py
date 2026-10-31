"""Staff, salaries and the month's pay (decision 099). Fictitious data only."""

import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core.isolamento import usar_clinica
from apps.core.models import MODULOS_GERAIS, ModuloClinico, Papel
from apps.core.modulos import configurar
from apps.financeiro import servicos as financeiro
from apps.financeiro.models import Lancamento
from apps.pessoal import servicos
from apps.pessoal.models import Folha, Funcionario, Salario, hora_extra_sugerida

pytestmark = pytest.mark.django_db

OUTUBRO = datetime.date(2026, 10, 1)
FOLHA = reverse("pessoal:folha")


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_pessoal", clinica_a, Papel.ADMIN))


@pytest.fixture
def ana(clinica_a):
    with usar_clinica(clinica_a):
        funcionario = Funcionario.objects.create(
            nome="Ana Fictícia", cargo="Recepcionista", admissao=datetime.date(2025, 3, 1)
        )
        Salario.objects.create(
            funcionario=funcionario, valor=Decimal("2200"), desde=datetime.date(2025, 3, 1)
        )
        return funcionario


def test_cadastro_com_salario_e_aumento_no_historico(clinica_a, admin):
    resposta = admin.post(
        reverse("pessoal:novo"),
        {
            "nome": "Bruno Fictício",
            "cpf": "529.982.247-25",
            "admissao": "2026-01-05",
            "salario": "3000",
            "ativo": "on",
        },
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        bruno = Funcionario.objects.get()
        assert bruno.cpf == "52998224725"
        assert bruno.salarios.get().desde == datetime.date(2026, 1, 5)  # admission date
    aumento = admin.post(
        reverse("pessoal:editar", args=[bruno.pk]),
        {
            "nome": "Bruno Fictício",
            "cpf": "52998224725",
            "admissao": "2026-01-05",
            "salario": "3300",
            "salario_desde": "2026-07-01",
            "ativo": "on",
        },
    )
    assert aumento.status_code == 302
    with usar_clinica(clinica_a):
        assert bruno.salario_em(datetime.date(2026, 6, 30)) == Decimal("3000")
        assert bruno.salario_em(datetime.date(2026, 7, 1)) == Decimal("3300")
        assert bruno.salarios.count() == 2


@pytest.mark.parametrize(
    ("dados", "campo"),
    [
        ({"cpf": "111.111.111-11"}, "cpf"),
        ({"salario": ""}, "salario"),
        ({"admissao": "2026-05-01", "desligamento": "2026-04-01"}, "desligamento"),
    ],
)
def test_validacoes_do_cadastro(dados, campo, admin):
    base = {"nome": "Fictício", "salario": "2000", "ativo": "on"}
    resposta = admin.post(reverse("pessoal:novo"), {**base, **dados})
    assert campo in resposta.context["form"].errors


def test_folha_prepara_os_funcionarios_do_mes(clinica_a, ana):
    with usar_clinica(clinica_a):
        futuro = Funcionario.objects.create(
            nome="Admitido depois", admissao=datetime.date(2026, 11, 3)
        )
        Salario.objects.create(
            funcionario=futuro, valor=Decimal("2000"), desde=datetime.date(2026, 11, 3)
        )
        saiu = Funcionario.objects.create(
            nome="Desligado antes", desligamento=datetime.date(2026, 9, 30)
        )
        Salario.objects.create(
            funcionario=saiu, valor=Decimal("2000"), desde=datetime.date(2025, 1, 1)
        )
        Funcionario.objects.create(nome="Sem salário")
        folhas = servicos.preparar(OUTUBRO)
    assert [f.funcionario.nome for f in folhas] == ["Ana Fictícia"]
    folha = folhas[0]
    assert folha.salario == Decimal("2200") and folha.valor_hora_extra == hora_extra_sugerida(
        Decimal("2200")
    ) == Decimal("15.00")


def test_olhar_um_mes_nao_grava_folhas(clinica_a, ana, admin):
    for mes in ("2026-10", "2030-01"):
        assert admin.get(FOLHA, {"mes": mes}).status_code == 200
    with usar_clinica(clinica_a):
        assert not Folha.objects.exists()


def test_calculo_do_total():
    folha = Folha(
        salario=Decimal("3000"),
        horas_extras=Decimal("10"),
        valor_hora_extra=Decimal("20.45"),
        faltas=2,
    )
    assert folha.valor_horas_extras == Decimal("204.50")
    assert folha.desconto_faltas == Decimal("200.00")
    assert folha.total == Decimal("3004.50")


def test_salvar_e_lancar_no_financeiro(clinica_a, ana, admin):
    pagina = admin.get(FOLHA, {"mes": "2026-10"})
    folha, form = pagina.context["linhas"][0]
    prefixo = form.prefix
    dados = {
        f"{prefixo}-horas_extras": "10",
        f"{prefixo}-valor_hora_extra": "15,00",
        f"{prefixo}-faltas": "1",
        f"{prefixo}-observacao": "",
    }
    assert folha.pk is None  # looking at the month stored nothing
    assert admin.post(f"{FOLHA}?mes=2026-10", dados).status_code == 302
    with usar_clinica(clinica_a):
        folha = Folha.objects.get(funcionario=ana, competencia=OUTUBRO)
        assert folha.total == Decimal("2276.67")  # 2200 + 150 − 73,33
        categoria = pagina.context["lancar_form"].fields["categoria"].initial
    assert categoria.nome == "Salários e encargos"
    resposta = admin.post(
        f"{FOLHA}?mes=2026-10",
        {**dados, "acao": "lancar", "categoria": categoria.pk, "vencimento": "2026-11-05"},
    )
    assert resposta.status_code == 302
    with usar_clinica(clinica_a):
        folha.refresh_from_db()
        lancamento = folha.lancamento
        assert (lancamento.tipo, lancamento.pessoa, lancamento.valor_total) == (
            Lancamento.Tipo.PAGAR,
            "Ana Fictícia",
            Decimal("2276.67"),
        )
        assert lancamento.parcelas.get().vencimento == datetime.date(2026, 11, 5)
    # A launched line is read-only and is not launched twice.
    linha = admin.get(FOLHA, {"mes": "2026-10"}).context["linhas"][0]
    assert linha[1] is None
    with usar_clinica(clinica_a):
        assert (
            servicos.lancar(
                [folha], categoria=categoria, vencimento=datetime.date(2026, 11, 5), usuario=None
            )
            == 0
        )
        # Cancelling the payable in finance opens the line again.
        financeiro.cancelar(lancamento, motivo="Refazer", usuario=None)
        folha.refresh_from_db()
        assert not folha.lancada


def test_total_zero_nao_e_lancado(clinica_a, ana):
    with usar_clinica(clinica_a):
        folha = servicos.preparar(OUTUBRO)[0]
        folha.faltas = 30
        folha.save()
        with pytest.raises(ValidationError, match="maior que zero"):
            servicos.lancar([folha], categoria=None, vencimento=OUTUBRO, usuario=None)


@pytest.mark.parametrize("papel", [Papel.RECEPCAO, Papel.PROFISSIONAL])
def test_so_administrador_e_financeiro_veem_salarios(
    papel, clinica_a, ana, criar_usuario, cliente_de
):
    cliente = cliente_de(criar_usuario("sem_pessoal", clinica_a, papel))
    for url in (FOLHA, reverse("pessoal:lista"), reverse("pessoal:funcionario", args=[ana.pk])):
        assert cliente.get(url).status_code == 403, url


def test_perfil_financeiro_lanca_a_folha(clinica_a, ana, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("fin_pessoal", clinica_a, Papel.FINANCEIRO))
    assert cliente.get(FOLHA).status_code == 200


def test_modulo_pessoal_liga_desliga_e_depende_do_financeiro(clinica_a, admin):
    assert reverse("pessoal:folha") in admin.get(reverse("inicio")).content.decode()
    configurar(clinica_a, MODULOS_GERAIS - {ModuloClinico.PESSOAL})
    assert admin.get(FOLHA).status_code == 403
    with pytest.raises(ValidationError):
        configurar(clinica_a, MODULOS_GERAIS - {ModuloClinico.FINANCEIRO, ModuloClinico.ORCAMENTOS})
