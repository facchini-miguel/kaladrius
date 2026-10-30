"""Chart of accounts (decision 097): groups in a tree, totals rolled up. Fictitious data."""

from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.financeiro import servicos
from apps.financeiro.models import Categoria, Conta, GrupoContabil, Lancamento

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_plano", clinica_a, Papel.ADMIN))


def grupo(clinica, nome, **extra):
    with usar_clinica(clinica):
        return GrupoContabil.objects.get(nome=nome, **extra)


def test_clinica_nova_comeca_com_o_plano_basico(clinica_a):
    with usar_clinica(clinica_a):
        aluguel = Categoria.objects.get(nome="Aluguel")
        assert str(aluguel.grupo) == "1 Ocupação"
        assert Categoria.objects.get(nome="Comissões").grupo.nome == "Pessoal"
        assert not Categoria.objects.filter(grupo=None).exists()
        assert GrupoContabil.objects.filter(tipo="receita").count() == 2


def test_subgrupo_numerado_e_categoria_movida(clinica_a, admin):
    pessoal = grupo(clinica_a, "Pessoal")
    resposta = admin.post(
        reverse("financeiro:grupo_novo"),
        {
            "nome": "Equipe da recepção",
            "tipo": "despesa",
            "pai": pessoal.pk,
            "codigo": 1,
            "ativo": "on",
        },
    )
    assert resposta.status_code == 302
    sub = grupo(clinica_a, "Equipe da recepção")
    with usar_clinica(clinica_a):
        assert sub.numero == "2.1"
        salarios = Categoria.objects.get(nome="Salários e encargos")
    editar = admin.post(
        reverse("financeiro:cadastro_editar", args=["categorias", salarios.pk]),
        {"nome": salarios.nome, "tipo": "despesa", "grupo": sub.pk, "ativa": "on"},
    )
    assert editar.status_code == 302
    pagina = admin.get(reverse("financeiro:plano_contas")).content.decode()
    assert "2.1 Equipe da recepção" in pagina and "Salários e encargos" in pagina


def test_validacoes_do_grupo(clinica_a, admin):
    pessoal = grupo(clinica_a, "Pessoal")
    atendimentos = grupo(clinica_a, "Atendimentos")
    url = reverse("financeiro:grupo_novo")
    misturado = admin.post(url, {"nome": "X", "tipo": "despesa", "pai": atendimentos.pk})
    assert "pai" in misturado.context["form"].errors
    repetido = admin.post(url, {"nome": "pessoal", "tipo": "despesa"})
    assert "nome" in repetido.context["form"].errors
    # A group cannot go under itself or under one of its subgroups.
    with usar_clinica(clinica_a):
        sub = GrupoContabil.objects.create(nome="Sub", tipo="despesa", pai=pessoal)
    ciclo = admin.post(
        reverse("financeiro:grupo_editar", args=[pessoal.pk]),
        {"nome": "Pessoal", "tipo": "despesa", "pai": sub.pk},
    )
    assert "pai" in ciclo.context["form"].errors


def test_categoria_nao_entra_em_grupo_de_outro_tipo(clinica_a, admin):
    resposta = admin.post(
        reverse("financeiro:cadastro_novo", args=["categorias"]),
        {
            "nome": "Exames",
            "tipo": "receita",
            "grupo": grupo(clinica_a, "Pessoal").pk,
            "ativa": "on",
        },
    )
    assert "grupo" in resposta.context["form"].errors


def test_relatorio_soma_os_subgrupos(clinica_a, admin):
    with usar_clinica(clinica_a):
        pessoal = GrupoContabil.objects.get(nome="Pessoal")
        sub = GrupoContabil.objects.create(nome="Recepção", tipo="despesa", pai=pessoal, codigo=1)
        salarios = Categoria.objects.get(nome="Salários e encargos")
        salarios.grupo = sub
        salarios.save()
        avulsa = Categoria.objects.create(nome="Despesa avulsa", tipo="despesa")
        caixa = Conta.objects.get(nome="Caixa")
        for categoria, valor in (
            (salarios, "1000"),
            (Categoria.objects.get(nome="Comissões"), "300"),
            (avulsa, "50"),
        ):
            lancamento = servicos.criar_lancamento(
                clinica=clinica_a,
                tipo=Lancamento.Tipo.PAGAR,
                pessoa="Fictício",
                descricao="Pagamento",
                categoria=categoria,
                valor_total=Decimal(valor),
                parcelas=1,
                primeiro_vencimento=HOJE,
                usuario=None,
            )
            parcela = lancamento.parcelas.get()
            servicos.receber(parcela, usuario=None, valor=parcela.valor, forma="pix", conta=caixa)
    relatorio = admin.get(reverse("financeiro:relatorios")).context["relatorio"]
    assert [(n, nome, str(v)) for n, nome, v in relatorio["despesas_por_grupo"]] == [
        (0, "2 Pessoal", "1300.00"),
        (1, "2.1 Recepção", "1000.00"),
        (0, "Sem grupo", "50.00"),
    ]


def test_quem_ve_o_plano(clinica_a, criar_usuario, cliente_de):
    recepcao = cliente_de(criar_usuario("recepcao_plano", clinica_a, Papel.RECEPCAO))
    assert recepcao.get(reverse("financeiro:plano_contas")).status_code == 403


@pytest.mark.django_db(transaction=True)
def test_migracao_cria_o_plano_basico_nas_clinicas_existentes():
    executor = MigrationExecutor(connection)
    folhas = executor.loader.graph.leaf_nodes()
    anterior = [("financeiro", "0011_fechamento")]
    try:
        executor.migrate(anterior)
        # Pessoal depends on the newer finance, so it is rolled back along with it.
        estado = [f for f in folhas if f[0] not in ("financeiro", "pessoal")] + anterior
        apps = executor.loader.project_state(estado).apps
        clinica = apps.get_model("core", "Clinica").objects.create(nome="Clínica fictícia antiga")
        Categoria = apps.get_model("financeiro", "Categoria")
        Categoria.objects.create(clinica_id=clinica.pk, nome="Aluguel", tipo="despesa")
        Categoria.objects.create(clinica_id=clinica.pk, nome="Aluguel da sala", tipo="despesa")
        executor = MigrationExecutor(connection)
        executor.migrate([("financeiro", "0012_plano_de_contas")])
        novos = executor.loader.project_state([("financeiro", "0012_plano_de_contas")]).apps
        Nova = novos.get_model("financeiro", "Categoria")
        assert Nova.objects.get(clinica_id=clinica.pk, nome="Aluguel").grupo.nome == "Ocupação"
        assert Nova.objects.get(clinica_id=clinica.pk, nome="Aluguel da sala").grupo is None
        Grupo = novos.get_model("financeiro", "GrupoContabil")
        assert Grupo.objects.filter(clinica_id=clinica.pk).count() == 7
    finally:
        MigrationExecutor(connection).migrate(folhas)
