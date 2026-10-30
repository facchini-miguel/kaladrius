import datetime
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.mark.django_db(transaction=True)
def test_migracao_preserva_as_areas_das_clinicas_existentes():
    executor = MigrationExecutor(connection)
    folhas = executor.loader.graph.leaf_nodes()
    anterior = [("core", "0009_papel_financeiro")]
    destino = [("core", "0010_modulos_clinicos")]
    try:
        executor.migrate(anterior)
        estado_anterior = [folha for folha in folhas if folha[0] != "core"] + anterior
        apps = executor.loader.project_state(estado_anterior).apps
        Clinica = apps.get_model("core", "Clinica")
        ids = {
            area: Clinica.objects.create(nome=f"Clínica fictícia {area}", area=area).pk
            for area in ("odontologia", "medicina", "outra")
        }
        clinica_id = ids["odontologia"]
        Paciente = apps.get_model("pacientes", "Paciente")
        paciente = Paciente.objects.create(
            clinica_id=clinica_id,
            nome="Paciente fictício anterior à atualização",
            observacoes="Texto inteiramente fictício preservado",
        )
        Categoria = apps.get_model("financeiro", "Categoria")
        categoria = Categoria.objects.create(
            clinica_id=clinica_id, nome="Receita fictícia", tipo="receita"
        )
        Lancamento = apps.get_model("financeiro", "Lancamento")
        lancamento = Lancamento.objects.create(
            clinica_id=clinica_id,
            tipo="receber",
            descricao="Tratamento fictício",
            categoria=categoria,
            paciente=paciente,
            valor_total=Decimal("123.45"),
        )
        Parcela = apps.get_model("financeiro", "Parcela")
        Parcela.objects.create(
            clinica_id=clinica_id,
            lancamento=lancamento,
            numero=1,
            vencimento=datetime.date(2026, 11, 10),
            valor=Decimal("123.45"),
        )
        Orcamento = apps.get_model("orcamentos", "Orcamento")
        orcamento = Orcamento.objects.create(clinica_id=clinica_id, paciente=paciente)
        Item = apps.get_model("orcamentos", "ItemOrcamento")
        Item.objects.create(
            clinica_id=clinica_id,
            orcamento=orcamento,
            descricao="Item dental fictício",
            dentes="11,12",
            faces="V",
            valor_unitario=Decimal("123.45"),
        )
        modelos = [Clinica, Paciente, Categoria, Lancamento, Parcela, Orcamento, Item]
        antes = {
            modelo._meta.label: list(modelo.objects.order_by("pk").values()) for modelo in modelos
        }
        executor = MigrationExecutor(connection)
        executor.migrate(destino)
        Modulo = executor.loader.project_state(destino).apps.get_model("core", "ModuloDaClinica")
        for area, codigo_clinica in ids.items():
            ativos = set(
                Modulo.objects.filter(clinica_id=codigo_clinica, ativo=True).values_list(
                    "codigo", flat=True
                )
            )
            assert ativos == ({area} if area != "outra" else set())
            assert Modulo.objects.filter(clinica_id=codigo_clinica).count() == 2
        atualizados = executor.loader.project_state(folhas).apps
        for label, registros in antes.items():
            modelo = atualizados.get_model(label)
            assert list(modelo.objects.order_by("pk").values()) == registros, label
    finally:
        MigrationExecutor(connection).migrate(folhas)
