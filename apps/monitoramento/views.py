import datetime

from django.contrib.auth.decorators import login_required
from django.db import connection
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import Backup

from . import saude

PERIODOS = {"24h": datetime.timedelta(hours=24), "7d": datetime.timedelta(days=7)}
# (title, [(key, css class, legend)], top of scale, unit): percentages use 0-100.
GRAFICOS = [
    (
        _("Processador"),
        [
            ("cpu", "linha-1", _("em uso")),
            ("cpu_roubada", "linha-2", _("tomado por outras máquinas")),
        ],
        100,
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


def _banco():
    """Database size and its largest tables."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        tamanho = cursor.fetchone()[0]
        cursor.execute(
            """
            SELECT relname, pg_total_relation_size(relid), n_live_tup
            FROM pg_stat_user_tables ORDER BY 2 DESC LIMIT 8
            """
        )
        tabelas = [
            {"nome": nome, "tamanho": tamanho_tabela, "registros": registros}
            for nome, tamanho_tabela, registros in cursor.fetchall()
        ]
    return {"tamanho": tamanho, "tabelas": tabelas}


@login_required
def painel(request):
    """Server health for superusers (other users get "not found", like the technical docs)."""
    if not request.user.is_superuser:
        raise Http404
    periodo = request.GET.get("periodo", "24h")
    if periodo not in PERIODOS:
        periodo = "24h"
    lista = saude.com_rede(saude.amostras(desde=timezone.now() - PERIODOS[periodo]))
    ultima = lista[-1] if lista else saude.ultima()
    graficos = []
    for titulo, series, maximo, unidade in GRAFICOS:
        linhas = [(chave, classe) for chave, classe, _legenda in series]
        graficos.append(
            {
                "titulo": titulo,
                "svg": saude.grafico(lista, linhas, maximo=maximo),
                "topo": saude.topo_da_escala(lista, linhas, maximo),
                "unidade": unidade,
                "legendas": [(classe, legenda) for _chave, classe, legenda in series],
            }
        )
    return render(
        request,
        "monitoramento/saude.html",
        {
            "periodo": periodo,
            "ultima": ultima,
            "niveis": saude.niveis(ultima) if ultima else {},
            "parada": saude.parada(ultima) if ultima else False,
            "ligado_desde": ultima["momento"] - datetime.timedelta(seconds=ultima["ligado_ha"])
            if ultima
            else None,
            "resumo": saude.resumo(lista),
            "graficos": graficos,
            "banco": _banco(),
            "backup": Backup.objects.first(),
        },
    )
