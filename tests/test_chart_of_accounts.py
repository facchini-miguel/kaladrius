"""Chart of accounts (decision 097): groups in a tree, totals rolled up. Fictitious data."""

from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.finance import services
from apps.finance.models import AccountGroup, Category, Entry, FinancialAccount
from tests.test_modules_migration import estado_do_banco

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_plano", clinica_a, Papel.ADMIN))


def grupo(clinic, name, **extra):
    with usar_clinica(clinic):
        return AccountGroup.objects.get(name=name, **extra)


def test_clinica_nova_comeca_com_o_plano_basico(clinica_a):
    with usar_clinica(clinica_a):
        aluguel = Category.objects.get(name="Aluguel")
        assert str(aluguel.grupo) == "1 Ocupação"
        assert Category.objects.get(name="Comissões").grupo.name == "Pessoal"
        assert not Category.objects.filter(grupo=None).exists()
        assert AccountGroup.objects.filter(kind="receita").count() == 2


def test_subgrupo_numerado_e_categoria_movida(clinica_a, admin):
    pessoal = grupo(clinica_a, "Pessoal")
    resposta = admin.post(
        reverse("finance:group_new"),
        {
            "name": "Equipe da recepção",
            "kind": "despesa",
            "pai": pessoal.pk,
            "code": 1,
            "active": "on",
        },
    )
    assert resposta.status_code == 302
    sub = grupo(clinica_a, "Equipe da recepção")
    with usar_clinica(clinica_a):
        assert sub.number == "2.1"
        salarios = Category.objects.get(name="Salários e encargos")
    editar = admin.post(
        reverse("finance:catalog_edit", args=["categories", salarios.pk]),
        {"name": salarios.name, "kind": "despesa", "grupo": sub.pk, "active": "on"},
    )
    assert editar.status_code == 302
    pagina = admin.get(reverse("finance:chart_of_accounts")).content.decode()
    assert "2.1 Equipe da recepção" in pagina and "Salários e encargos" in pagina


def test_codigo_em_branco_recebe_o_proximo_numero(clinica_a, admin):
    """Review stage 3: a subgroup saved with a blank code had no number at all."""
    pessoal = grupo(clinica_a, "Pessoal")
    for name in ("Equipe A", "Equipe B"):
        dados = {"name": name, "kind": "despesa", "pai": pessoal.pk, "code": "", "active": "on"}
        assert admin.post(reverse("finance:group_new"), dados).status_code == 302
    with usar_clinica(clinica_a):
        assert grupo(clinica_a, "Equipe A").number == "2.1"
        assert grupo(clinica_a, "Equipe B").number == "2.2"
    # A new top group goes after the five of the basic plan.
    topo = {"name": "Investimentos", "kind": "despesa", "pai": "", "code": "", "active": "on"}
    assert admin.post(reverse("finance:group_new"), topo).status_code == 302
    with usar_clinica(clinica_a):
        assert grupo(clinica_a, "Investimentos").number == "6"


def test_validacoes_do_grupo(clinica_a, admin):
    pessoal = grupo(clinica_a, "Pessoal")
    atendimentos = grupo(clinica_a, "Atendimentos")
    url = reverse("finance:group_new")
    misturado = admin.post(url, {"name": "X", "kind": "despesa", "pai": atendimentos.pk})
    assert "pai" in misturado.context["form"].errors
    repetido = admin.post(url, {"name": "pessoal", "kind": "despesa"})
    assert "name" in repetido.context["form"].errors
    # A group cannot go under itself or under one of its subgroups.
    with usar_clinica(clinica_a):
        sub = AccountGroup.objects.create(name="Sub", kind="despesa", pai=pessoal)
    ciclo = admin.post(
        reverse("finance:group_edit", args=[pessoal.pk]),
        {"name": "Pessoal", "kind": "despesa", "pai": sub.pk},
    )
    assert "pai" in ciclo.context["form"].errors


def test_categoria_nao_entra_em_grupo_de_outro_tipo(clinica_a, admin):
    resposta = admin.post(
        reverse("finance:catalog_new", args=["categories"]),
        {
            "name": "Exames",
            "kind": "receita",
            "grupo": grupo(clinica_a, "Pessoal").pk,
            "active": "on",
        },
    )
    assert "grupo" in resposta.context["form"].errors


def test_relatorio_soma_os_subgrupos(clinica_a, admin):
    with usar_clinica(clinica_a):
        pessoal = AccountGroup.objects.get(name="Pessoal")
        sub = AccountGroup.objects.create(name="Recepção", kind="despesa", pai=pessoal, code=1)
        salarios = Category.objects.get(name="Salários e encargos")
        salarios.grupo = sub
        salarios.save()
        avulsa = Category.objects.create(name="Despesa avulsa", kind="despesa")
        caixa = FinancialAccount.objects.get(name="Caixa")
        for categoria, amount in (
            (salarios, "1000"),
            (Category.objects.get(name="Comissões"), "300"),
            (avulsa, "50"),
        ):
            entry = services.criar_lancamento(
                clinic=clinica_a,
                kind=Entry.Tipo.PAGAR,
                pessoa="Fictício",
                description="Pagamento",
                categoria=categoria,
                valor_total=Decimal(amount),
                parcelas=1,
                primeiro_vencimento=HOJE,
                user=None,
            )
            parcela = entry.parcelas.get()
            services.receber(parcela, user=None, amount=parcela.amount, forma="pix", account=caixa)
    relatorio = admin.get(reverse("finance:reports")).context["relatorio"]
    assert [(n, name, str(v)) for n, name, v in relatorio["despesas_por_grupo"]] == [
        (0, "2 Pessoal", "1300.00"),
        (1, "2.1 Recepção", "1000.00"),
        (0, "Sem grupo", "50.00"),
    ]


def test_quem_ve_o_plano(clinica_a, criar_usuario, cliente_de):
    recepcao = cliente_de(criar_usuario("recepcao_plano", clinica_a, Papel.RECEPCAO))
    assert recepcao.get(reverse("finance:chart_of_accounts")).status_code == 403


@pytest.mark.django_db(transaction=True)
def test_migracao_cria_o_plano_basico_nas_clinicas_existentes():
    executor = MigrationExecutor(connection)
    folhas = executor.loader.graph.leaf_nodes()
    anterior = [("financeiro", "0011_fechamento")]
    try:
        executor.migrate(anterior)
        # Pessoal and the renames of decision 157 depend on the newer finance, so they were
        # rolled back along with it.
        apps = estado_do_banco()
        clinic = apps.get_model("core", "Clinica").objects.create(nome="Clínica fictícia antiga")
        Category = apps.get_model("financeiro", "Categoria")
        Category.objects.create(clinica_id=clinic.pk, nome="Aluguel", tipo="despesa")
        Category.objects.create(clinica_id=clinic.pk, nome="Aluguel da sala", tipo="despesa")
        executor = MigrationExecutor(connection)
        executor.migrate([("financeiro", "0012_plano_de_contas")])
        novos = executor.loader.project_state([("financeiro", "0012_plano_de_contas")]).apps
        Nova = novos.get_model("financeiro", "Categoria")
        assert Nova.objects.get(clinica_id=clinic.pk, nome="Aluguel").grupo.nome == "Ocupação"
        assert Nova.objects.get(clinica_id=clinic.pk, nome="Aluguel da sala").grupo is None
        Grupo = novos.get_model("financeiro", "GrupoContabil")
        assert Grupo.objects.filter(clinica_id=clinic.pk).count() == 7
    finally:
        MigrationExecutor(connection).migrate(folhas)
