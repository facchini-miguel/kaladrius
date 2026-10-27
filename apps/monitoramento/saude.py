"""Server health read from the samples of deploy/servidor/saude.sh (0.22.0, decision 056).

The server collects them every 5 minutes with plain Linux tools and keeps 7 days in a
JSON-lines file mounted read-only in the app container (settings.SAUDE_DIR). Nothing is
stored in the database.
"""

import datetime
import json
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.safestring import mark_safe

ARQUIVO = "amostras.jsonl"
COLETA_PARADA_APOS = datetime.timedelta(minutes=20)
# A gap longer than this between samples breaks the chart line (collection was down).
LACUNA = datetime.timedelta(minutes=15)
# % in use: (attention, critical).
LIMITES = {"memoria": (85, 95), "swap": (50, 80), "disco": (80, 90), "cpu": (80, 95)}


def _arquivo():
    return Path(settings.SAUDE_DIR) / ARQUIVO


def _ler(linha):
    try:
        amostra = json.loads(linha)
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


def amostras(desde=None):
    """Samples in time order, optionally only those since `desde`."""
    try:
        linhas = _arquivo().read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    lidas = (_ler(linha) for linha in linhas)
    return [a for a in lidas if a is not None and (desde is None or a["momento"] >= desde)]


def ultima():
    """The newest sample, reading only the end of the file (used on every superuser page)."""
    try:
        with _arquivo().open("rb") as arquivo:
            arquivo.seek(0, 2)
            arquivo.seek(max(0, arquivo.tell() - 16384))
            linhas = arquivo.read().decode("utf-8", errors="ignore").splitlines()
    except OSError:
        return None
    for linha in reversed(linhas):
        amostra = _ler(linha)
        if amostra is not None:
            return amostra
    return None


def nivel(chave, valor):
    atencao, critico = LIMITES[chave]
    if valor >= critico:
        return "critico"
    if valor >= atencao:
        return "atencao"
    return "ok"


def niveis(amostra):
    return {
        "cpu": nivel("cpu", amostra["cpu"]),
        "memoria": nivel("memoria", amostra["memoria_pct"]),
        "swap": nivel("swap", amostra["swap_pct"]),
        "disco": nivel("disco", amostra["disco_pct"]),
    }


def parada(amostra, agora=None):
    return (agora or timezone.now()) - amostra["momento"] > COLETA_PARADA_APOS


def com_rede(lista):
    """Add rede_entrada / rede_saida (bytes per second since the previous sample)."""
    anterior = None
    for amostra in lista:
        amostra["rede_entrada"] = amostra["rede_saida"] = None
        if anterior is not None:
            segundos = (amostra["momento"] - anterior["momento"]).total_seconds()
            recebido = amostra["rede_recebido"] - anterior["rede_recebido"]
            enviado = amostra["rede_enviado"] - anterior["rede_enviado"]
            # Counters restart at zero when the server reboots.
            if 0 < segundos and recebido >= 0 and enviado >= 0:
                amostra["rede_entrada"] = recebido / segundos
                amostra["rede_saida"] = enviado / segundos
        anterior = amostra
    return lista


def resumo(lista):
    """Average and peaks of a period (None without samples)."""
    if not lista:
        return None
    com_rede(lista)
    entradas = [a for a in lista if a["rede_entrada"] is not None]
    return {
        "amostras": len(lista),
        "inicio": lista[0]["momento"],
        "fim": lista[-1]["momento"],
        "cpu_media": sum(a["cpu"] for a in lista) / len(lista),
        "cpu_maxima": max(a["cpu"] for a in lista),
        "memoria_maxima": max(a["memoria_pct"] for a in lista),
        "swap_maximo": max(a["swap_pct"] for a in lista),
        "disco": lista[-1]["disco_pct"],
        "recebido": sum(
            a["rede_entrada"] * (a["momento"] - b["momento"]).total_seconds()
            for b, a in zip(lista, lista[1:], strict=False)
            if a["rede_entrada"] is not None
        ),
        "enviado": sum(
            a["rede_saida"] * (a["momento"] - b["momento"]).total_seconds()
            for b, a in zip(lista, lista[1:], strict=False)
            if a["rede_saida"] is not None
        ),
        "rede_maxima": max((a["rede_entrada"] + a["rede_saida"] for a in entradas), default=0),
    }


def topo_da_escala(lista, series, maximo=None, piso=None):
    """The value at the top of a chart: fixed (`maximo`), or following the data, at least
    `piso` and never above the `teto` of percentages (so 0.5% of CPU is still visible)."""
    if maximo:
        return maximo
    valores = [a[chave] for a in lista for chave, _ in series if a.get(chave) is not None]
    topo = max(max(valores, default=0) * 1.2, piso or 0)
    return topo or 1


def grafico(
    lista,
    series,
    *,
    inicio=None,
    fim=None,
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
    pontos = [a for a in lista if any(a.get(chave) is not None for chave, _ in series)]
    if not pontos:
        return ""
    inicio = inicio or pontos[0]["momento"]
    fim = fim or pontos[-1]["momento"]
    duracao = max((fim - inicio).total_seconds(), 1)
    topo = topo_da_escala(lista, series, maximo, piso)
    if teto:
        topo = min(topo, teto)
    margem = 4  # lines at 0 or at the top stay visible

    def x(momento):
        if fim == inicio:
            return largura / 2
        return (momento - inicio).total_seconds() / duracao * largura

    def y(valor):
        return altura - margem - min(valor, topo) / topo * (altura - 2 * margem)

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
    for chave, classe in reversed(series):
        trechos, atual, anterior = [], [], None
        for amostra in lista:
            valor = amostra.get(chave)
            if valor is None:
                continue
            if anterior is not None and amostra["momento"] - anterior > LACUNA and atual:
                trechos.append(atual)
                atual = []
            atual.append(f"{x(amostra['momento']):.1f},{y(valor):.1f}")
            anterior = amostra["momento"]
        if atual:
            trechos.append(atual)
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
