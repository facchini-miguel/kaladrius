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
            ("cpu", "linha-1", _("em uso")),
            ("cpu_roubada", "linha-2", _("tomado por outras máquinas")),
        ],
        None,
        "%",
    ),
    (
        _("Memória"),
        [
            ("memoria_pct", "linha-1", _("memória em uso")),
            ("swap_pct", "linha-2", _("swap em uso")),
        ],
        100,
        "%",
    ),
    (_("Disco"), [("disco_pct", "linha-1", _("em uso"))], 100, "%"),
    (
        _("Rede"),
        [
            ("rede_entrada", "linha-1", _("recebido por segundo")),
            ("rede_saida", "linha-2", _("enviado por segundo")),
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
            {"name": name, "size": tamanho_tabela, "registros": registros}
            for name, tamanho_tabela, registros in cursor.fetchall()
        ]
    return {"size": size, "tabelas": tables}


@login_required
def health_dashboard(request):
    """Server health for every logged-in user (0.26.0). The database tables and the server
    command are shown to superusers only."""
    periodo = request.GET.get("periodo", "1h")
    if periodo not in PERIODS:
        periodo = "1h"
    # The time axis is the whole period, even while there are fewer samples.
    end = timezone.now()
    start = end - PERIODS[periodo]
    results = health.with_network(health.samples(desde=start))
    latest = results[-1] if results else health.latest()
    graficos = []
    for titulo, series, maximo, unidade in CHARTS:
        rows = [(key, classe) for key, classe, _legenda in series]
        piso, teto = (10, 100) if unidade == "%" else (None, None)
        topo = health.scale_top(results, rows, maximo, piso)
        graficos.append(
            {
                "titulo": titulo,
                "svg": health.chart(
                    results, rows, start=start, end=end, maximo=maximo, piso=piso, teto=teto
                ),
                "topo": min(topo, teto) if teto else topo,
                "unidade": unidade,
                "legendas": [(classe, legenda) for _chave, classe, legenda in series],
            }
        )
    return render(
        request,
        "monitoring/health.html",
        {
            "periodo": periodo,
            "start": start,
            "end": end,
            "ultima": latest,
            "niveis": health.levels(latest) if latest else {},
            "parada": health.stopped(latest) if latest else False,
            "ligado_desde": latest["momento"] - datetime.timedelta(seconds=latest["ligado_ha"])
            if latest
            else None,
            "resumo": health.summary(results),
            "graficos": graficos,
            "banco": _database(),
            "backup": Backup.objects.first(),
        },
    )
