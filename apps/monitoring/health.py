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
# health.sh writes the fields in English, and they are the names used here (decision 186). Lines
# from before health.sh wrote English (no "time") carry the old Portuguese names.
OLD_FIELDS = {
    "momento": "time",
    "cpu_roubada": "cpu_steal",
    "carga": "load",
    "memoria_total": "memory_total",
    "memoria_disponivel": "memory_available",
    "swap_livre": "swap_free",
    "disco_total": "disk_total",
    "disco_usado": "disk_used",
    "rede_recebido": "network_received",
    "rede_enviado": "network_sent",
    "ligado_ha": "uptime",
}
OLD_CONTAINER_FIELDS = {"nome": "name", "memoria": "memory", "memoria_pct": "memory_pct"}
COLLECTION_STOPPED_AFTER = datetime.timedelta(minutes=20)
# A gap longer than this between samples breaks the chart line (collection was down).
GAP = datetime.timedelta(minutes=15)
# % in use: (attention, critical).
THRESHOLDS = {"memory": (85, 95), "swap": (50, 80), "disk": (80, 90), "cpu": (80, 95)}


def _file():
    return Path(settings.HEALTH_DIR) / FILE_NAME


def _read(row):
    try:
        sample = json.loads(row)
        if "time" not in sample:
            sample = {OLD_FIELDS.get(key, key): value for key, value in sample.items()}
            sample["containers"] = [
                {OLD_CONTAINER_FIELDS.get(key, key): value for key, value in c.items()}
                for c in sample.get("containers", [])
            ]
        sample["time"] = parse_datetime(sample["time"])
        if sample["time"] is None:
            return None
        total = sample["memory_total"] or 1
        sample["memory_used"] = total - sample["memory_available"]
        sample["memory_pct"] = 100 * sample["memory_used"] / total
        sample["swap_used"] = sample["swap_total"] - sample["swap_free"]
        sample["swap_pct"] = (
            100 * sample["swap_used"] / sample["swap_total"] if sample["swap_total"] else 0
        )
        sample["disk_pct"] = 100 * sample["disk_used"] / (sample["disk_total"] or 1)
        return sample
    except (ValueError, KeyError, TypeError):
        return None  # a line cut while being written, or from an older format


def samples(since=None):
    """Samples in time order, optionally only those since `desde`."""
    try:
        rows = _file().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    parsed = (_read(row) for row in rows)
    return [a for a in parsed if a is not None and (since is None or a["time"] >= since)]


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
        sample = _read(row)
        if sample is not None:
            return sample
    return None


def level(key, value):
    warning, critical = THRESHOLDS[key]
    if value >= critical:
        return "critico"
    if value >= warning:
        return "atencao"
    return "ok"


def levels(sample):
    return {
        "cpu": level("cpu", sample["cpu"]),
        "memory": level("memory", sample["memory_pct"]),
        "swap": level("swap", sample["swap_pct"]),
        "disk": level("disk", sample["disk_pct"]),
    }


def stopped(sample, now=None):
    return (now or timezone.now()) - sample["time"] > COLLECTION_STOPPED_AFTER


def with_network(results):
    """Add network_in / network_out (bytes per second since the previous sample)."""
    previous = None
    for sample in results:
        sample["network_in"] = sample["network_out"] = None
        if previous is not None:
            seconds = (sample["time"] - previous["time"]).total_seconds()
            received = sample["network_received"] - previous["network_received"]
            sent = sample["network_sent"] - previous["network_sent"]
            # Counters restart at zero when the server reboots.
            if 0 < seconds and received >= 0 and sent >= 0:
                sample["network_in"] = received / seconds
                sample["network_out"] = sent / seconds
        previous = sample
    return results


def summary(results):
    """Average and peaks of a period (None without samples)."""
    if not results:
        return None
    with_network(results)
    inflows = [a for a in results if a["network_in"] is not None]
    return {
        "samples": len(results),
        "start": results[0]["time"],
        "end": results[-1]["time"],
        "cpu_avg": sum(a["cpu"] for a in results) / len(results),
        "cpu_max": max(a["cpu"] for a in results),
        "memory_max": max(a["memory_pct"] for a in results),
        "swap_max": max(a["swap_pct"] for a in results),
        "disk": results[-1]["disk_pct"],
        "received": sum(
            a["network_in"] * (a["time"] - b["time"]).total_seconds()
            for b, a in zip(results, results[1:], strict=False)
            if a["network_in"] is not None
        ),
        "sent": sum(
            a["network_out"] * (a["time"] - b["time"]).total_seconds()
            for b, a in zip(results, results[1:], strict=False)
            if a["network_out"] is not None
        ),
        "network_max": max((a["network_in"] + a["network_out"] for a in inflows), default=0),
    }


def scale_top(results, series, maximum=None, floor=None):
    """The value at the top of a chart: fixed (`maximo`), or following the data, at least
    `piso` and never above the `teto` of percentages (so 0.5% of CPU is still visible)."""
    if maximum:
        return maximum
    values = [a[key] for a in results for key, _ in series if a.get(key) is not None]
    top = max(max(values, default=0) * 1.2, floor or 0)
    return top or 1


def chart(
    results,
    series,
    *,
    start=None,
    end=None,
    maximum=None,
    floor=None,
    ceiling=None,
    width=720,
    height=140,
):
    """Line chart as inline SVG: `series` = [(key, css class)], the main one first.

    The time axis goes from `inicio` to `fim` (the chosen period), or spans the samples.
    Long gaps (collection down) break the lines; an isolated point becomes a dot. The
    scale is fixed with `maximo`, or follows the data (at least `piso`, at most `teto`).
    """
    points = [a for a in results if any(a.get(key) is not None for key, _ in series)]
    if not points:
        return ""
    start = start or points[0]["time"]
    end = end or points[-1]["time"]
    duration = max((end - start).total_seconds(), 1)
    top = scale_top(results, series, maximum, floor)
    if ceiling:
        top = min(top, ceiling)
    margin = 4  # lines at 0 or at the top stay visible

    def x(timestamp):
        if end == start:
            return width / 2
        return (timestamp - start).total_seconds() / duration * width

    def y(value):
        return height - margin - min(value, top) / top * (height - 2 * margin)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" preserveAspectRatio="none" class="chart" '
        f'role="img" aria-hidden="true">',
        *(
            f'<line x1="0" x2="{width}" y1="{height * f:.1f}" y2="{height * f:.1f}" '
            'class="grid-line"/>'
            for f in (0.25, 0.5, 0.75)
        ),
    ]
    # The main series is drawn last, on top of the others.
    for key, css_class in reversed(series):
        segments, current, previous = [], [], None
        for sample in results:
            value = sample.get(key)
            if value is None:
                continue
            if previous is not None and sample["time"] - previous > GAP and current:
                segments.append(current)
                current = []
            current.append(f"{x(sample['time']):.1f},{y(value):.1f}")
            previous = sample["time"]
        if current:
            segments.append(current)
        for segment in segments:
            if len(segment) == 1:
                px, py = segment[0].split(",")
                parts.append(f'<circle cx="{px}" cy="{py}" r="3" class="{css_class}"/>')
            else:
                parts.append(
                    f'<polyline points="{" ".join(segment)}" class="{css_class}" '
                    'vector-effect="non-scaling-stroke"/>'
                )
    parts.append("</svg>")
    return mark_safe("".join(parts))  # noqa: S308 (only numbers and fixed class names)
