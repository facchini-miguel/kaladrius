"""Server health read from the samples of deploy/server/health.sh (0.22.0, decision 056).

The server collects them every 5 minutes with plain Linux tools and keeps 7 days in a
JSON-lines file mounted read-only in the app container (settings.HEALTH_DIR). Nothing is
stored in the database. The fields are in English since decision 149; a line written before
(Portuguese fields, kept up to 7 days) is read too. Here they all get the internal names.
"""

import datetime
import json
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.safestring import mark_safe

FILE_NAME = "samples.jsonl"
# The fields of a sample and of each of its containers, as health.sh writes them: internal names.
FIELDS = {
    "time": "momento",
    "cpu_steal": "cpu_roubada",
    "load": "carga",
    "memory_total": "memoria_total",
    "memory_available": "memoria_disponivel",
    "swap_free": "swap_livre",
    "disk_total": "disco_total",
    "disk_used": "disco_usado",
    "network_received": "rede_recebido",
    "network_sent": "rede_enviado",
    "uptime": "ligado_ha",
}
CONTAINER_FIELDS = {"name": "nome", "memory": "memoria", "memory_pct": "memoria_pct"}
COLLECTION_STOPPED_AFTER = datetime.timedelta(minutes=20)
# A gap longer than this between samples breaks the chart line (collection was down).
GAP = datetime.timedelta(minutes=15)
# % in use: (attention, critical).
THRESHOLDS = {"memoria": (85, 95), "swap": (50, 80), "disco": (80, 90), "cpu": (80, 95)}


def _file():
    return Path(settings.HEALTH_DIR) / FILE_NAME


def _read(row):
    try:
        amostra = json.loads(row)
        if "time" in amostra:
            amostra = {FIELDS.get(key, key): value for key, value in amostra.items()}
            amostra["containers"] = [
                {CONTAINER_FIELDS.get(key, key): value for key, value in c.items()}
                for c in amostra.get("containers", [])
            ]
        amostra["momento"] = parse_datetime(amostra["momento"])
        if amostra["momento"] is None:
            return None
        total = amostra["memoria_total"] or 1
        amostra["memoria_usada"] = total - amostra["memoria_disponivel"]
        amostra["memoria_pct"] = 100 * amostra["memoria_usada"] / total
        amostra["swap_usado"] = amostra["swap_total"] - amostra["swap_livre"]
        amostra["swap_pct"] = (
            100 * amostra["swap_usado"] / amostra["swap_total"] if amostra["swap_total"] else 0
        )
        amostra["disco_pct"] = 100 * amostra["disco_usado"] / (amostra["disco_total"] or 1)
        return amostra
    except (ValueError, KeyError, TypeError):
        return None  # a line cut while being written, or from an older format


def samples(desde=None):
    """Samples in time order, optionally only those since `desde`."""
    try:
        rows = _file().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    lidas = (_read(row) for row in rows)
    return [a for a in lidas if a is not None and (desde is None or a["momento"] >= desde)]


def latest():
    """The newest sample, reading only the end of the file (used on every superuser page)."""
    try:
        with _file().open("rb") as file:
            file.seek(0, 2)
            file.seek(max(0, file.tell() - 16384))
            rows = file.read().decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    for row in reversed(rows):
        amostra = _read(row)
        if amostra is not None:
            return amostra
    return None


def level(key, value):
    atencao, critico = THRESHOLDS[key]
    if value >= critico:
        return "critico"
    if value >= atencao:
        return "atencao"
    return "ok"


def levels(amostra):
    return {
        "cpu": level("cpu", amostra["cpu"]),
        "memoria": level("memoria", amostra["memoria_pct"]),
        "swap": level("swap", amostra["swap_pct"]),
        "disco": level("disco", amostra["disco_pct"]),
    }


def stopped(amostra, now=None):
    return (now or timezone.now()) - amostra["momento"] > COLLECTION_STOPPED_AFTER


def with_network(results):
    """Add rede_entrada / rede_saida (bytes per second since the previous sample)."""
    previous = None
    for amostra in results:
        amostra["rede_entrada"] = amostra["rede_saida"] = None
        if previous is not None:
            segundos = (amostra["momento"] - previous["momento"]).total_seconds()
            recebido = amostra["rede_recebido"] - previous["rede_recebido"]
            enviado = amostra["rede_enviado"] - previous["rede_enviado"]
            # Counters restart at zero when the server reboots.
            if 0 < segundos and recebido >= 0 and enviado >= 0:
                amostra["rede_entrada"] = recebido / segundos
                amostra["rede_saida"] = enviado / segundos
        previous = amostra
    return results


def summary(results):
    """Average and peaks of a period (None without samples)."""
    if not results:
        return None
    with_network(results)
    entradas = [a for a in results if a["rede_entrada"] is not None]
    return {
        "amostras": len(results),
        "start": results[0]["momento"],
        "end": results[-1]["momento"],
        "cpu_media": sum(a["cpu"] for a in results) / len(results),
        "cpu_maxima": max(a["cpu"] for a in results),
        "memoria_maxima": max(a["memoria_pct"] for a in results),
        "swap_maximo": max(a["swap_pct"] for a in results),
        "disco": results[-1]["disco_pct"],
        "recebido": sum(
            a["rede_entrada"] * (a["momento"] - b["momento"]).total_seconds()
            for b, a in zip(results, results[1:], strict=False)
            if a["rede_entrada"] is not None
        ),
        "enviado": sum(
            a["rede_saida"] * (a["momento"] - b["momento"]).total_seconds()
            for b, a in zip(results, results[1:], strict=False)
            if a["rede_saida"] is not None
        ),
        "rede_maxima": max((a["rede_entrada"] + a["rede_saida"] for a in entradas), default=0),
    }


def scale_top(results, series, maximo=None, piso=None):
    """The value at the top of a chart: fixed (`maximo`), or following the data, at least
    `piso` and never above the `teto` of percentages (so 0.5% of CPU is still visible)."""
    if maximo:
        return maximo
    valores = [a[key] for a in results for key, _ in series if a.get(key) is not None]
    topo = max(max(valores, default=0) * 1.2, piso or 0)
    return topo or 1


def chart(
    results,
    series,
    *,
    start=None,
    end=None,
    maximo=None,
    piso=None,
    teto=None,
    largura=720,
    altura=140,
):
    """Line chart as inline SVG: `series` = [(key, css class)], the main one first.

    The time axis goes from `inicio` to `fim` (the chosen period), or spans the samples.
    Long gaps (collection down) break the lines; an isolated point becomes a dot. The
    scale is fixed with `maximo`, or follows the data (at least `piso`, at most `teto`).
    """
    pontos = [a for a in results if any(a.get(key) is not None for key, _ in series)]
    if not pontos:
        return ""
    start = start or pontos[0]["momento"]
    end = end or pontos[-1]["momento"]
    duration = max((end - start).total_seconds(), 1)
    topo = scale_top(results, series, maximo, piso)
    if teto:
        topo = min(topo, teto)
    margem = 4  # lines at 0 or at the top stay visible

    def x(timestamp):
        if end == start:
            return largura / 2
        return (timestamp - start).total_seconds() / duration * largura

    def y(value):
        return altura - margem - min(value, topo) / topo * (altura - 2 * margem)

    partes = [
        f'<svg viewBox="0 0 {largura} {altura}" preserveAspectRatio="none" class="grafico" '
        f'role="img" aria-hidden="true">',
        *(
            f'<line x1="0" x2="{largura}" y1="{altura * f:.1f}" y2="{altura * f:.1f}" '
            'class="grade"/>'
            for f in (0.25, 0.5, 0.75)
        ),
    ]
    # The main series is drawn last, on top of the others.
    for key, classe in reversed(series):
        trechos, current, previous = [], [], None
        for amostra in results:
            value = amostra.get(key)
            if value is None:
                continue
            if previous is not None and amostra["momento"] - previous > GAP and current:
                trechos.append(current)
                current = []
            current.append(f"{x(amostra['momento']):.1f},{y(value):.1f}")
            previous = amostra["momento"]
        if current:
            trechos.append(current)
        for trecho in trechos:
            if len(trecho) == 1:
                px, py = trecho[0].split(",")
                partes.append(f'<circle cx="{px}" cy="{py}" r="3" class="{classe}"/>')
            else:
                partes.append(
                    f'<polyline points="{" ".join(trecho)}" class="{classe}" '
                    'vector-effect="non-scaling-stroke"/>'
                )
    partes.append("</svg>")
    return mark_safe("".join(partes))  # noqa: S308 (only numbers and fixed class names)
