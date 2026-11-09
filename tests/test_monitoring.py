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


def sample(minutes_ago, *, available=400, swap_free=900, disk=5, network=0, cpu=5.0):
    timestamp = timezone.now() - datetime.timedelta(minutes=minutes_ago)
    return json.dumps(
        {
            "momento": timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cpu": cpu,
            "cpu_roubada": 0.5,
            "carga": [0.1, 0.1, 0.1],
            "memoria_total": 1000 * MB,
            "memoria_disponivel": available * MB,
            "swap_total": 1000 * MB,
            "swap_livre": swap_free * MB,
            "disco_total": 30 * 1024 * MB,
            "disco_usado": disk * 1024 * MB,
            "rede_recebido": network,
            "rede_enviado": network * 2,
            "ligado_ha": 3600,
            "containers": [
                {"nome": "app", "cpu": "1%", "memoria": "180MiB / 1GiB", "memoria_pct": "18%"}
            ],
        }
    )


@pytest.fixture
def folder(tmp_path, settings):
    settings.HEALTH_DIR = str(tmp_path)
    settings.HEALTH_MONITORED = True

    def write_file(*rows):
        (tmp_path / health.FILE_NAME).write_text("\n".join(rows) + "\n", encoding="utf-8")

    return write_file


@pytest.fixture
def superuser(client, django_user_model):
    client.force_login(django_user_model.objects.create_superuser("root", password="x-123456789"))
    return client


def test_reads_samples_skips_cut_line_and_computes_percentages(folder):
    folder(sample(10, available=250, swap_free=750), '{"momento": "2026-10-27T1')
    (read_one,) = health.samples()
    assert (read_one["memory_pct"], read_one["swap_pct"]) == (75, 25)
    assert round(read_one["disk_pct"]) == 17
    assert health.latest()["memory_pct"] == 75


def english_sample(minutes_ago, **values_):
    """The same sample with the fields health.sh writes since decision 149."""
    old_one = json.loads(sample(minutes_ago, **values_))
    new_one = {health.OLD_FIELDS.get(key, key): value for key, value in old_one.items()}
    new_one["containers"] = [
        {health.OLD_CONTAINER_FIELDS.get(key, key): value for key, value in c.items()}
        for c in old_one["containers"]
    ]
    return json.dumps(new_one)


def test_reads_english_and_old_samples(folder):
    # The file keeps up to 7 days: right after the update, lines of both formats.
    folder(sample(20, available=250), english_sample(10, available=250, swap_free=750))
    old_one, new_one = health.samples()
    assert "time" in english_sample(10)
    assert (new_one["memory_pct"], new_one["swap_pct"]) == (75, 25)
    assert new_one["time"] > old_one["time"]
    assert new_one["containers"] == old_one["containers"]
    assert health.latest()["memory_pct"] == 75


def test_network_per_second_and_server_restart(folder):
    folder(sample(10, network=0), sample(5, network=300_000), sample(0, network=1000))  # reboot
    results = health.with_network(health.samples())
    assert results[1]["network_in"] == pytest.approx(1000, rel=0.01)  # 300 kB in 300 s
    assert results[2]["network_in"] is None
    assert health.summary(results)["received"] == pytest.approx(300_000, rel=0.01)


def test_levels_and_stopped_collection(folder):
    folder(sample(30, available=30, swap_free=400, disk=28))
    latest = health.latest()
    assert health.levels(latest) == {
        "cpu": "ok",
        "memory": "critical",
        "swap": "warning",
        "disk": "critical",
    }
    assert health.stopped(latest)


def test_chart_breaks_the_line_at_the_gap(folder):
    folder(sample(120), sample(115), sample(10), sample(5))
    svg = health.chart(health.samples(), [("cpu", "line-1")], maximum=100)
    assert svg.count("<polyline") == 2


def test_screen_for_everyone_without_technical_details(folder, clinic_a, create_user, client_for):
    folder(sample(5))
    reception = client_for(create_user("recepcao", clinic_a, Role.FRONT_DESK))
    assert 'href="/system/health/"' in reception.get(reverse("home")).content.decode()
    page = reception.get(reverse("monitoring:health"))
    assert page.status_code == 200
    content = page.content.decode()
    assert "<svg" in content and "Nenhum backup registrado" in content
    assert "Maiores tabelas" not in content and "health.sh" not in content


def test_screen_with_samples(folder, superuser):
    folder(*(sample(m, network=m * 1000) for m in range(60, -1, -5)))
    for period_ in ("1h", "24h", "7d", "outro"):
        page = superuser.get(reverse("monitoring:health"), {"period": period_})
        assert page.status_code == 200
    content = page.content.decode()
    assert "<svg" in content and "app" in content and "Maiores tabelas" in content
    assert page.context["period"] == "1h"  # the default
    assert page.context["end"] - page.context["start"] == datetime.timedelta(hours=1)


def test_screen_without_samples(settings, tmp_path, superuser):
    settings.HEALTH_DIR = str(tmp_path / "nao-existe")
    page = superuser.get(reverse("monitoring:health")).content.decode()
    assert "Ainda não há amostras" in page


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        ([], {"no_samples": True}),
        ([sample(60)], "stopped"),
        ([sample(1, available=20, cpu=99)], {"critical": ["memory"]}),  # not the CPU
        ([sample(1)], None),
    ],
)
def test_warning_at_the_top(folder, superuser, rows, expected):
    if rows:
        folder(*rows)
    context = superuser.get(reverse("whats_new")).context
    health_alert = context.get("health_alert")
    if expected == "stopped":
        assert "stopped" in health_alert
    else:
        assert health_alert == expected


def test_warning_names_the_critical_resource(folder, superuser):
    # Decision 186 made the keys English; the warning compared them with the old words and
    # called every resource "processador".
    folder(sample(1, available=20, disk=29))
    page = superuser.get(reverse("whats_new")).content.decode()
    assert "recursos no limite: memória, disco." in page


def test_command_summarizes_24_hours(folder):
    folder(sample(10, cpu=4), sample(5, cpu=8, disk=29))
    output = StringIO()
    call_command("health", stdout=output)
    text = output.getvalue()
    assert "Samples: 2" in text and "peak 8.0%" in text
    assert "disk: critical" in text and "Last backup: none recorded" in text


def test_scale_follows_data_and_lone_point_becomes_dot(folder):
    folder(sample(10, network=0, cpu=0.5), sample(5, network=1000, cpu=0.5))
    results = health.with_network(health.samples())
    # 0.5% of CPU on a 0-100 scale would be a flat line: the top follows the data.
    assert health.scale_top(results, [("cpu", "line-1")], floor=10) == 10
    assert health.scale_top(results, [("cpu", "line-1")], maximum=100) == 100
    # Only the second sample has a network rate: one point, drawn as a dot.
    svg = health.chart(results, [("network_in", "line-1")])
    assert "<circle" in svg and "<polyline" not in svg
    # The main series (first) is drawn last, on top.
    svg = health.chart(results, [("cpu", "line-1"), ("cpu_steal", "line-2")], floor=10)
    assert svg.rindex("line-1") > svg.rindex("line-2")


def test_time_axis_is_the_whole_period(folder):
    folder(sample(10), sample(5))
    now = timezone.now()
    svg = health.chart(
        health.samples(),
        [("cpu", "line-1")],
        start=now - datetime.timedelta(hours=1),
        end=now,
        maximum=100,
    )
    # 10 minutes of samples on a 1-hour axis: the line starts near the right end.
    first_x = float(svg.split('points="')[1].split(",")[0])
    assert 580 < first_x < 620


def test_health_for_monitors_queries_the_database(client, monkeypatch):
    # Decision 079: the external monitor needs the database to answer, not only Django.
    from django.db import OperationalError

    response = client.get("/api/v1/health")
    assert response.status_code == 200 and response.json()["database"] is True

    import config.api

    class BrokenCursor:
        def __enter__(self):
            raise OperationalError("banco fora")

        def __exit__(self, *error):
            return False

    monkeypatch.setattr(config.api.connection, "cursor", lambda: BrokenCursor())
    response = client.get("/api/v1/health")
    assert response.status_code == 503 and response.json() == {"database": False}
