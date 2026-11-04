import datetime
from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


def estado_do_banco():
    """The models as the database is now: each app at its last applied migration. Taking core
    back also undoes the later migrations of the apps that depend on it (pacientes 0004 on)."""
    executor = MigrationExecutor(connection)
    aplicadas = set(executor.loader.applied_migrations)
    grafo = executor.loader.graph
    ultimas = [
        no
        for no in aplicadas
        if no in grafo.nodes
        and not any(f in aplicadas and f[0] == no[0] for f in grafo.node_map[no].children)
    ]
    return executor.loader.project_state(ultimas).apps


@pytest.mark.django_db(transaction=True)
def test_migracao_preserva_as_areas_das_clinicas_existentes():
    executor = MigrationExecutor(connection)
    folhas = executor.loader.graph.leaf_nodes()
    anterior = [("core", "0009_papel_financeiro")]
    destino = [("core", "0010_modulos_clinicos")]
    try:
        executor.migrate(anterior)
        apps = estado_do_banco()
        Clinic = apps.get_model("core", "Clinica")
        ids = {
            area: Clinic.objects.create(nome=f"Clínica fictícia {area}", area=area).pk
            for area in ("odontologia", "medicina", "outra")
        }
        clinic_id = ids["odontologia"]
        Patient = apps.get_model("pacientes", "Paciente")
        paciente = Patient.objects.create(
            clinica_id=clinic_id,
            nome="Paciente fictício anterior à atualização",
            observacoes="Texto inteiramente fictício preservado",
        )
        Category = apps.get_model("financeiro", "Categoria")
        categoria = Category.objects.create(
            clinica_id=clinic_id, nome="Receita fictícia", tipo="receita"
        )
        Entry = apps.get_model("financeiro", "Lancamento")
        lancamento = Entry.objects.create(
            clinica_id=clinic_id,
            tipo="receber",
            descricao="Tratamento fictício",
            categoria=categoria,
            paciente=paciente,
            valor_total=Decimal("123.45"),
        )
        Installment = apps.get_model("financeiro", "Parcela")
        Installment.objects.create(
            clinica_id=clinic_id,
            lancamento=lancamento,
            numero=1,
            vencimento=datetime.date(2026, 11, 10),
            valor=Decimal("123.45"),
        )
        Estimate = apps.get_model("orcamentos", "Orcamento")
        orcamento = Estimate.objects.create(clinica_id=clinic_id, paciente=paciente)
        Item = apps.get_model("orcamentos", "ItemOrcamento")
        Item.objects.create(
            clinica_id=clinic_id,
            orcamento=orcamento,
            descricao="Item dental fictício",
            dentes="11,12",
            faces="V",
            valor_unitario=Decimal("123.45"),
        )
        modelos = [Clinic, Patient, Category, Entry, Installment, Estimate, Item]
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
        # The models as the database is now: core's later migrations add columns that do not
        # exist yet.
        atualizados = estado_do_banco()
        for label, registros in antes.items():
            modelo = atualizados.get_model(label)
            assert list(modelo.objects.order_by("pk").values()) == registros, label
    finally:
        MigrationExecutor(connection).migrate(folhas)
