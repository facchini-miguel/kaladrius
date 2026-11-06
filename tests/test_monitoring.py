"""Server health page (0.22.0): samples from deploy/server/health.sh."""

import datetime
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Role
from apps.monitoring import health

pytestmark = pytest.mark.django_db
MB = 2**20


def amostra(minutos_atras, *, disponivel=400, swap_livre=900, disco=5, rede=0, cpu=5.0):
    timestamp = timezone.now() - datetime.timedelta(minutes=minutos_atras)
    return json.dumps(
        {
            "momento": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cpu": cpu,
            "cpu_roubada": 0.5,
            "carga": [0.1, 0.1, 0.1],
            "memoria_total": 1000 * MB,
            "memoria_disponivel": disponivel * MB,
            "swap_total": 1000 * MB,
            "swap_livre": swap_livre * MB,
            "disco_total": 30 * 1024 * MB,
            "disco_usado": disco * 1024 * MB,
            "rede_recebido": rede,
            "rede_enviado": rede * 2,
            "ligado_ha": 3600,
            "containers": [
                {"nome": "app", "cpu": "1%", "memoria": "180MiB / 1GiB", "memoria_pct": "18%"}
            ],
        }
    )


@pytest.fixture
def pasta(tmp_path, settings):
    settings.HEALTH_DIR = str(tmp_path)
    settings.HEALTH_MONITORED = True

    def gravar(*rows):
        (tmp_path / health.FILE_NAME).write_text("\n".join(rows) + "\n", encoding="utf-8")

    return gravar


@pytest.fixture
def superusuario(client, django_user_model):
    client.force_login(django_user_model.objects.create_superuser("root", password="x-123456789"))
    return client


def test_reads_samples_skips_cut_line_and_computes_percentages(pasta):
    pasta(amostra(10, disponivel=250, swap_livre=750), '{"momento": "2026-10-27T1')
    (lida,) = health.samples()
    assert (lida["memoria_pct"], lida["swap_pct"]) == (75, 25)
    assert round(lida["disco_pct"]) == 17
    assert health.latest()["memoria_pct"] == 75


def amostra_em_ingles(minutos_atras, **valores):
    """The same sample with the fields health.sh writes since decision 149."""
    antiga = json.loads(amostra(minutos_atras, **valores))
    nomes = {interno: field for field, interno in health.FIELDS.items()}
    nova = {nomes.get(key, key): value for key, value in antiga.items()}
    nomes_container = {interno: field for field, interno in health.CONTAINER_FIELDS.items()}
    nova["containers"] = [
        {nomes_container.get(key, key): value for key, value in c.items()}
        for c in antiga["containers"]
    ]
    return json.dumps(nova)


def test_reads_english_and_old_samples(pasta):
    # The file keeps up to 7 days: right after the update, lines of both formats.
    pasta(amostra(20, disponivel=250), amostra_em_ingles(10, disponivel=250, swap_livre=750))
    antiga, nova = health.samples()
    assert "time" in amostra_em_ingles(10)
    assert (nova["memoria_pct"], nova["swap_pct"]) == (75, 25)
    assert nova["momento"] > antiga["momento"]
    assert nova["containers"] == antiga["containers"]
    assert health.latest()["memoria_pct"] == 75


def test_network_per_second_and_server_restart(pasta):
    pasta(amostra(10, rede=0), amostra(5, rede=300_000), amostra(0, rede=1000))  # reboot
    results = health.with_network(health.samples())
    assert results[1]["rede_entrada"] == pytest.approx(1000, rel=0.01)  # 300 kB in 300 s
    assert results[2]["rede_entrada"] is None
    assert health.summary(results)["recebido"] == pytest.approx(300_000, rel=0.01)


def test_levels_and_stopped_collection(pasta):
    pasta(amostra(30, disponivel=30, swap_livre=400, disco=28))
    latest = health.latest()
    assert health.levels(latest) == {
        "cpu": "ok",
        "memoria": "critico",
        "swap": "atencao",
        "disco": "critico",
    }
    assert health.stopped(latest)


def test_chart_breaks_the_line_at_the_gap(pasta):
    pasta(amostra(120), amostra(115), amostra(10), amostra(5))
    svg = health.chart(health.samples(), [("cpu", "line-1")], maximo=100)
    assert svg.count("<polyline") == 2


def test_screen_for_everyone_without_technical_details(pasta, clinica_a, criar_usuario, cliente_de):
    pasta(amostra(5))
    reception = cliente_de(criar_usuario("recepcao", clinica_a, Role.FRONT_DESK))
    assert 'href="/system/health/"' in reception.get(reverse("home")).content.decode()
    page = reception.get(reverse("monitoring:health"))
    assert page.status_code == 200
    content = page.content.decode()
    assert "<svg" in content and "Nenhum backup registrado" in content
    assert "Maiores tabelas" not in content and "health.sh" not in content


def test_screen_with_samples(pasta, superusuario):
    pasta(*(amostra(m, rede=m * 1000) for m in range(60, -1, -5)))
    for periodo in ("1h", "24h", "7d", "outro"):
        page = superusuario.get(reverse("monitoring:health"), {"period": periodo})
        assert page.status_code == 200
    content = page.content.decode()
    assert "<svg" in content and "app" in content and "Maiores tabelas" in content
    assert page.context["period"] == "1h"  # the default
    assert page.context["end"] - page.context["start"] == datetime.timedelta(hours=1)


def test_screen_without_samples(settings, tmp_path, superusuario):
    settings.HEALTH_DIR = str(tmp_path / "nao-existe")
    page = superusuario.get(reverse("monitoring:health")).content.decode()
    assert "Ainda não há amostras" in page


@pytest.mark.parametrize(
    ("rows", "esperado"),
    [
        ([], {"sem_coleta": True}),
        ([amostra(60)], "parada"),
        ([amostra(1, disponivel=20, cpu=99)], {"criticos": ["memoria"]}),  # not the CPU
        ([amostra(1)], None),
    ],
)
def test_warning_at_the_top(pasta, superusuario, rows, esperado):
    if rows:
        pasta(*rows)
    context = superusuario.get(reverse("whats_new")).context
    health_alert = context.get("saude_alerta")
    if esperado == "parada":
        assert "parada" in health_alert
    else:
        assert health_alert == esperado


def test_command_summarizes_24_hours(pasta):
    pasta(amostra(10, cpu=4), amostra(5, cpu=8, disco=29))
    saida = StringIO()
    call_command("health", stdout=saida)
    text = saida.getvalue()
    assert "Amostras: 2" in text and "pico 8.0%" in text
    assert "disco: critico" in text and "Último backup: nenhum registrado" in text


def test_scale_follows_data_and_lone_point_becomes_dot(pasta):
    pasta(amostra(10, rede=0, cpu=0.5), amostra(5, rede=1000, cpu=0.5))
    results = health.with_network(health.samples())
    # 0.5% of CPU on a 0-100 scale would be a flat line: the top follows the data.
    assert health.scale_top(results, [("cpu", "line-1")], piso=10) == 10
    assert health.scale_top(results, [("cpu", "line-1")], maximo=100) == 100
    # Only the second sample has a network rate: one point, drawn as a dot.
    svg = health.chart(results, [("rede_entrada", "line-1")])
    assert "<circle" in svg and "<polyline" not in svg
    # The main series (first) is drawn last, on top.
    svg = health.chart(results, [("cpu", "line-1"), ("cpu_roubada", "line-2")], piso=10)
    assert svg.rindex("line-1") > svg.rindex("line-2")


def test_time_axis_is_the_whole_period(pasta):
    pasta(amostra(10), amostra(5))
    now = timezone.now()
    svg = health.chart(
        health.samples(),
        [("cpu", "line-1")],
        start=now - datetime.timedelta(hours=1),
        end=now,
        maximo=100,
    )
    # 10 minutes of samples on a 1-hour axis: the line starts near the right end.
    primeiro_x = float(svg.split('points="')[1].split(",")[0])
    assert 580 < primeiro_x < 620


def test_health_for_monitors_queries_the_database(client, monkeypatch):
    # Decision 079: the external monitor needs the database to answer, not only Django.
    from django.db import OperationalError

    response = client.get("/api/v1/health")
    assert response.status_code == 200 and response.json()["database"] is True
    assert client.get("/api/v1/saude").json()["banco"] is True  # the old address (decision 155)

    import config.api

    class CursorQuebrado:
        def __enter__(self):
            raise OperationalError("banco fora")

        def __exit__(self, *error):
            return False

    monkeypatch.setattr(config.api.connection, "cursor", lambda: CursorQuebrado())
    response = client.get("/api/v1/health")
    assert response.status_code == 503 and response.json() == {"database": False}
    response = client.get("/api/v1/saude")
    assert response.status_code == 503 and response.json() == {"banco": False}
