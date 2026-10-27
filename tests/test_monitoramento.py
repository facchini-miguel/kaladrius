"""Server health page (0.22.0): samples from deploy/servidor/saude.sh."""

import datetime
import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Papel
from apps.monitoramento import saude

pytestmark = pytest.mark.django_db
MB = 2**20


def amostra(minutos_atras, *, disponivel=400, swap_livre=900, disco=5, rede=0, cpu=5.0):
    momento = timezone.now() - datetime.timedelta(minutes=minutos_atras)
    return json.dumps(
        {
            "momento": momento.strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    settings.SAUDE_DIR = str(tmp_path)
    settings.SAUDE_MONITORADA = True

    def gravar(*linhas):
        (tmp_path / saude.ARQUIVO).write_text("\n".join(linhas) + "\n", encoding="utf-8")

    return gravar


@pytest.fixture
def superusuario(client, django_user_model):
    client.force_login(django_user_model.objects.create_superuser("root", password="x-123456789"))
    return client


def test_le_amostras_ignora_linha_cortada_e_calcula_percentuais(pasta):
    pasta(amostra(10, disponivel=250, swap_livre=750), '{"momento": "2026-10-27T1')
    (lida,) = saude.amostras()
    assert (lida["memoria_pct"], lida["swap_pct"]) == (75, 25)
    assert round(lida["disco_pct"]) == 17
    assert saude.ultima()["memoria_pct"] == 75


def test_rede_por_segundo_e_reinicio_do_servidor(pasta):
    pasta(amostra(10, rede=0), amostra(5, rede=300_000), amostra(0, rede=1000))  # reboot
    lista = saude.com_rede(saude.amostras())
    assert lista[1]["rede_entrada"] == pytest.approx(1000, rel=0.01)  # 300 kB in 300 s
    assert lista[2]["rede_entrada"] is None
    assert saude.resumo(lista)["recebido"] == pytest.approx(300_000, rel=0.01)


def test_niveis_e_coleta_parada(pasta):
    pasta(amostra(30, disponivel=30, swap_livre=400, disco=28))
    ultima = saude.ultima()
    assert saude.niveis(ultima) == {
        "cpu": "ok",
        "memoria": "critico",
        "swap": "atencao",
        "disco": "critico",
    }
    assert saude.parada(ultima)


def test_grafico_quebra_a_linha_na_lacuna(pasta):
    pasta(amostra(120), amostra(115), amostra(10), amostra(5))
    svg = saude.grafico(saude.amostras(), [("cpu", "linha-1")], maximo=100)
    assert svg.count("<polyline") == 2


def test_tela_so_para_superusuario(pasta, client, clinica_a, criar_usuario, cliente_de):
    pasta(amostra(5))
    admin = cliente_de(criar_usuario("admin", clinica_a, Papel.ADMIN))
    assert admin.get(reverse("monitoramento:saude")).status_code == 404


def test_tela_com_amostras(pasta, superusuario):
    pasta(*(amostra(m, rede=m * 1000) for m in range(60, -1, -5)))
    for periodo in ("1h", "24h", "7d", "outro"):
        pagina = superusuario.get(reverse("monitoramento:saude"), {"periodo": periodo})
        assert pagina.status_code == 200
    conteudo = pagina.content.decode()
    assert "<svg" in conteudo and "app" in conteudo and "Maiores tabelas" in conteudo
    assert pagina.context["periodo"] == "1h"  # the default
    assert pagina.context["fim"] - pagina.context["inicio"] == datetime.timedelta(hours=1)


def test_tela_sem_amostras(settings, tmp_path, superusuario):
    settings.SAUDE_DIR = str(tmp_path / "nao-existe")
    pagina = superusuario.get(reverse("monitoramento:saude")).content.decode()
    assert "Ainda não há amostras" in pagina


@pytest.mark.parametrize(
    ("linhas", "esperado"),
    [
        ([], {"sem_coleta": True}),
        ([amostra(60)], "parada"),
        ([amostra(1, disponivel=20, cpu=99)], {"criticos": ["memoria"]}),  # not the CPU
        ([amostra(1)], None),
    ],
)
def test_aviso_no_topo(pasta, superusuario, linhas, esperado):
    if linhas:
        pasta(*linhas)
    contexto = superusuario.get(reverse("novidades")).context
    alerta = contexto.get("saude_alerta")
    if esperado == "parada":
        assert "parada" in alerta
    else:
        assert alerta == esperado


def test_comando_resume_as_24_horas(pasta):
    pasta(amostra(10, cpu=4), amostra(5, cpu=8, disco=29))
    saida = StringIO()
    call_command("saude", stdout=saida)
    texto = saida.getvalue()
    assert "Amostras: 2" in texto and "pico 8.0%" in texto
    assert "disco: critico" in texto and "Último backup: nenhum registrado" in texto


def test_escala_segue_os_dados_e_ponto_isolado_vira_bolinha(pasta):
    pasta(amostra(10, rede=0, cpu=0.5), amostra(5, rede=1000, cpu=0.5))
    lista = saude.com_rede(saude.amostras())
    # 0.5% of CPU on a 0-100 scale would be a flat line: the top follows the data.
    assert saude.topo_da_escala(lista, [("cpu", "linha-1")], piso=10) == 10
    assert saude.topo_da_escala(lista, [("cpu", "linha-1")], maximo=100) == 100
    # Only the second sample has a network rate: one point, drawn as a dot.
    svg = saude.grafico(lista, [("rede_entrada", "linha-1")])
    assert "<circle" in svg and "<polyline" not in svg
    # The main series (first) is drawn last, on top.
    svg = saude.grafico(lista, [("cpu", "linha-1"), ("cpu_roubada", "linha-2")], piso=10)
    assert svg.rindex("linha-1") > svg.rindex("linha-2")


def test_eixo_do_tempo_e_o_periodo_inteiro(pasta):
    pasta(amostra(10), amostra(5))
    agora = timezone.now()
    svg = saude.grafico(
        saude.amostras(),
        [("cpu", "linha-1")],
        inicio=agora - datetime.timedelta(hours=1),
        fim=agora,
        maximo=100,
    )
    # 10 minutes of samples on a 1-hour axis: the line starts near the right end.
    primeiro_x = float(svg.split('points="')[1].split(",")[0])
    assert 580 < primeiro_x < 620
