"""Migration core 0010 turned each existing clinic's area into its clinical module."""

import importlib

import pytest
from django.db import connection

from apps.core.isolation import without_isolation
from apps.core.models import Clinic, ClinicModule
from tests.era import apps_at, tables_of_the_time

pytestmark = pytest.mark.django_db

migracao = importlib.import_module("apps.core.migrations.0010_modulos_clinicos")


def test_migration_keeps_areas_of_existing_clinics():
    # Clinics as they were before 0010: an area and no modules.
    ids = {
        area: Clinic.objects.create(name=f"Clínica fictícia {area}", area=area).pk
        for area in ("odontologia", "medicina", "outra")
    }
    ClinicModule.all_objects.filter(clinic_id__in=ids.values()).delete()
    antes = list(Clinic.objects.filter(pk__in=ids.values()).order_by("pk").values())

    apps = apps_at(("core", "0010_modulos_clinicos"))
    pares = [
        (apps.get_model("core", "Clinica"), Clinic),
        (apps.get_model("core", "ModuloDaClinica"), ClinicModule),
    ]
    with tables_of_the_time(pares), connection.schema_editor() as editor:
        migracao.habilitar_areas_existentes(apps, editor)

    with without_isolation():
        for area, clinic_id in ids.items():
            ativos = set(
                ClinicModule.objects.filter(clinic_id=clinic_id, active=True).values_list(
                    "code", flat=True
                )
            )
            assert ativos == ({area} if area != "outra" else set())
            assert ClinicModule.objects.filter(clinic_id=clinic_id).count() == 2
    # The clinics themselves are not touched.
    assert list(Clinic.objects.filter(pk__in=ids.values()).order_by("pk").values()) == antes
