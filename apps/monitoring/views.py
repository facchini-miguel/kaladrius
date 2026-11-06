import datetime

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import Backup

from . import health

PERIODS = {
    "1h": datetime.timedelta(hours=1),
    "24h": datetime.timedelta(hours=24),
    "7d": datetime.timedelta(days=7),
}
# (title, [(key, css class, legend)], fixed top of scale, unit). Memory and disk use 0-100%;
# the processor follows the data (at least 10%), or 0.5% would be a flat line.
CHARTS = [
    (
        _("Processador"),
        [
            ("cpu", "line-1", _("em uso")),
            ("cpu_steal", "line-2", _("tomado por outras máquinas")),
        ],
        None,
        "%",
    ),
    (
        _("Memória"),
        [
            ("memory_pct", "line-1", _("memória em uso")),
            ("swap_pct", "line-2", _("swap em uso")),
        ],
        100,
        "%",
    ),
    (_("Disco"), [("disk_pct", "line-1", _("em uso"))], 100, "%"),
    (
        _("Rede"),
        [
            ("network_in", "line-1", _("recebido por segundo")),
            ("network_out", "line-2", _("enviado por segundo")),
        ],
        None,
        "bytes",
    ),
]


def _database():
    """Database size and its largest tables."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        size = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT relname, pg_total_relation_size(relid), n_live_tup
            FROM pg_stat_user_tables ORDER BY 2 DESC LIMIT 8
            """
        )
        tables = [
            {"name": name, "size": table_size, "row_count": records}
            for name, table_size, records in cursor.fetchall()
        ]
    return {"size": size, "tables": tables}


@login_required
def health_dashboard(request):
    """Server health for every logged-in user (0.26.0). The database tables and the server
    command are shown to superusers only."""
    period = request.GET.get("period", "1h")
    if period not in PERIODS:
        period = "1h"
    # The time axis is the whole period, even while there are fewer samples.
    end = timezone.now()
    start = end - PERIODS[period]
    results = health.with_network(health.samples(since=start))
    latest = results[-1] if results else health.latest()
    charts = []
    for title, series, maximum, unit in CHARTS:
        rows = [(key, css_class) for key, css_class, _legend in series]
        floor, ceiling = (10, 100) if unit == "%" else (None, None)
        top = health.scale_top(results, rows, maximum, floor)
        charts.append(
            {
                "title": title,
                "svg": health.chart(
                    results,
                    rows,
                    start=start,
                    end=end,
                    maximum=maximum,
                    floor=floor,
                    ceiling=ceiling,
                ),
                "top": min(top, ceiling) if ceiling else top,
                "unit": unit,
                "legends": [(css_class, legend) for _key, css_class, legend in series],
            }
        )
    return render(
        request,
        "monitoring/health.html",
        {
            "period": period,
            "start": start,
            "end": end,
            "latest": latest,
            "levels": health.levels(latest) if latest else {},
            "stopped": health.stopped(latest) if latest else False,
            "up_since": latest["time"] - datetime.timedelta(seconds=latest["uptime"])
            if latest
            else None,
            "summary": health.summary(results),
            "charts": charts,
            "database": _database(),
            "backup": Backup.objects.first(),
        },
    )
