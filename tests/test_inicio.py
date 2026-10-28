"""Home page summary of the day (0.24.0)."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.agenda import servicos as agenda
from apps.agenda.models import Agendamento, TipoAtendimento
from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.financeiro import servicos as financeiro
from apps.financeiro.models import Caixa, Categoria, Conta, Lancamento
from apps.orcamentos.models import Orcamento
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada

pytestmark = pytest.mark.django_db

# A Wednesday, 10:30 in the clinic's time zone.
HOJE = datetime.date(2031, 3, 5)
AGORA = timezone.make_aware(datetime.datetime(2031, 3, 5, 10, 30))


def dia(numero, mes=3):
    return datetime.date(2031, mes, numero)


@pytest.fixture
def cenario(monkeypatch, clinica_a, criar_profissional, criar_usuario):
    monkeypatch.setattr(timezone, "now", lambda: AGORA)
    ana = criar_profissional(clinica_a, "Dra. Ana")
    bruno = criar_profissional(clinica_a, "Dr. Bruno")
    usuarios = {
        "admin": criar_usuario("admin", clinica_a, Papel.ADMIN),
        "recepcao": criar_usuario("recepcao", clinica_a, Papel.RECEPCAO),
        "dra": criar_usuario("dra", clinica_a, Papel.PROFISSIONAL),
    }
    with usar_clinica(clinica_a):
        Profissional.objects.filter(pk=ana.pk).update(usuario=usuarios["dra"])
        tipo = TipoAtendimento.objects.get(nome="Cirurgia")
        maria = Paciente.objects.create(
            nome="Maria Paciente",
            data_nascimento=dia(5, 3).replace(year=1990),
            telefone_celular="11987654321",
        )
        joao = Paciente.objects.create(nome="João Paciente")
        arquivado = Paciente.objects.create(
            nome="Paciente Arquivado", arquivado=True, data_nascimento=dia(5).replace(year=1980)
        )

        def agendar(data, hora, profissional=ana, paciente=maria, situacao="agendado"):
            Agendamento.objects.create(
                profissional=profissional,
                tipo=tipo,
                paciente=paciente,
                descricao="" if paciente else "Bloqueado",
                situacao=situacao,
                inicio=agenda.momento(data, datetime.time(hora)),
                fim=agenda.momento(data, datetime.time(hora + 1)),
            )

        agendar(HOJE, 8, situacao="compareceu")
        agendar(HOJE, 9, situacao="faltou")
        agendar(HOJE, 10, profissional=bruno, paciente=joao)  # started, nobody marked it
        agendar(HOJE, 11)
        agendar(HOJE, 14, situacao="desmarcou")
        agendar(HOJE, 16, paciente=None)
        agendar(dia(3), 9, situacao="compareceu")
        agendar(dia(4), 9, situacao="faltou")
        agendar(dia(27, 2), 9, situacao="faltou")  # last month: not in this month's rate

        for data, concluida, paciente in [
            (HOJE, False, maria),
            (dia(1), False, maria),
            (dia(2), True, maria),
            (HOJE, False, arquivado),
            (dia(10), False, maria),
        ]:
            Rechamada.objects.create(
                paciente=paciente, data=data, descricao="Revisão", concluida=concluida
            )

        for paciente, validade, situacao in [
            (maria, dia(8), Orcamento.Situacao.ABERTO),
            (maria, dia(20), Orcamento.Situacao.ABERTO),
            (maria, dia(6), Orcamento.Situacao.APROVADO),
            (arquivado, dia(6), Orcamento.Situacao.ABERTO),
            (maria, dia(4), Orcamento.Situacao.ABERTO),
        ]:
            Orcamento.objects.create(
                paciente=paciente, data=dia(1), validade=validade, situacao=situacao
            )

        caixa = Conta.objects.get(nome="Caixa")
        receita = Categoria.objects.get(nome="Tratamento")
        despesa = Categoria.objects.get(nome="Outras despesas")

        def lancar(tipo, valor, parcelas, vencimento, categoria, **campos):
            lancamento = financeiro.criar_lancamento(
                clinica=clinica_a,
                tipo=tipo,
                descricao="Teste",
                categoria=categoria,
                valor_total=Decimal(valor),
                parcelas=parcelas,
                primeiro_vencimento=vencimento,
                usuario=usuarios["admin"],
                **campos,
            )
            return list(lancamento.parcelas.order_by("numero"))

        def pagar(parcela, valor, data, forma="pix"):
            financeiro.receber(
                parcela,
                usuario=usuarios["admin"],
                valor=Decimal(valor),
                data=data,
                forma=forma,
                conta=caixa,
            )

        # Due 05/01, 05/02 (overdue) and today; the first one is paid today.
        primeira, _segunda, _terceira = lancar(
            Lancamento.Tipo.RECEBER, "300", 3, dia(5, 1), receita, paciente=maria
        )
        pagar(primeira, "100", HOJE)
        [fevereiro] = lancar(Lancamento.Tipo.RECEBER, "200", 1, dia(3, 2), receita, paciente=joao)
        pagar(fevereiro, "200", dia(3, 2), forma="dinheiro")
        [conta_de_luz] = lancar(Lancamento.Tipo.PAGAR, "50", 1, HOJE, despesa, pessoa="Luz")
        pagar(conta_de_luz, "50", HOJE)
        lancar(Lancamento.Tipo.PAGAR, "80", 1, dia(10), despesa, pessoa="Aluguel")
        lancar(Lancamento.Tipo.PAGAR, "999", 1, dia(20), despesa, pessoa="Longe")
        Caixa.objects.create(conta=caixa, valor_abertura=Decimal("0"), aberto_por=usuarios["admin"])
    return {"clinica": clinica_a, **usuarios}


def inicio(cenario, cliente_de, quem):
    return cliente_de(cenario[quem]).get(reverse("inicio"))


def test_recepcao_ve_o_dia_sem_as_despesas(cenario, cliente_de):
    resposta = inicio(cenario, cliente_de, "recepcao")
    painel = resposta.context["painel"]
    dia_ = painel["agenda"]
    assert len(dia_["lista"]) == 6 and dia_["mostrar_profissional"]
    assert (dia_["pacientes"], dia_["compareceram"], dia_["faltaram"]) == (4, 1, 1)
    assert (dia_["desmarcaram"], dia_["a_seguir"], dia_["sem_marcacao"]) == (1, 1, 1)
    assert dia_["proximo"].paciente.nome == "João Paciente"  # 10:00–11:00, still going on
    # Month so far: came 08:00 today and on the 3rd; missed 09:00 today and on the 4th.
    assert (dia_["faltas_mes"], dia_["marcados_mes"]) == (50, 4)

    recebimentos = painel["recebimentos"]
    assert recebimentos["recebido"] == Decimal("100")
    assert recebimentos["por_forma"] == [("Pix", Decimal("100"))]
    assert (recebimentos["a_receber"], recebimentos["parcelas_a_receber"]) == (Decimal("100"), 1)
    assert [caixa.conta.nome for caixa in recebimentos["caixas"]] == ["Caixa"]
    assert "financeiro" not in painel

    conteudo = resposta.content.decode()
    assert "Bom dia, recepcao" in conteudo
    assert "Recebido hoje" in conteudo and "Pago hoje" not in conteudo
    assert "Saldo nas contas" not in conteudo
    assert reverse("agenda:situacao", args=[dia_["proximo"].pk]) in conteudo


def test_administrador_ve_resultado_do_dia_e_do_mes(cenario, cliente_de):
    painel = inicio(cenario, cliente_de, "admin").context["painel"]
    fin = painel["financeiro"]
    assert fin["pago_hoje"] == Decimal("50") and fin["resultado_hoje"] == Decimal("50")
    assert (fin["recebido_mes"], fin["pago_mes"]) == (Decimal("100"), Decimal("50"))
    assert fin["resultado_mes"] == Decimal("50")
    # Same days of February (1st to 5th): the 200 received on the 3rd.
    assert (fin["inicio_anterior"], fin["ate_anterior"]) == (dia(1, 2), dia(5, 2))
    assert fin["resultado_anterior"] == Decimal("200")
    assert (fin["vencido"], fin["parcelas_vencidas"]) == (Decimal("100"), 1)
    assert (fin["a_pagar"], fin["contas_a_pagar"]) == (Decimal("80"), 1)
    assert fin["saldo_contas"] == Decimal("250")


def test_profissional_ve_so_a_propria_agenda_e_nenhum_valor(cenario, cliente_de):
    resposta = inicio(cenario, cliente_de, "dra")
    painel = resposta.context["painel"]
    assert {a.profissional.nome for a in painel["agenda"]["lista"]} == {"Dra. Ana"}
    assert not painel["agenda"]["mostrar_profissional"]
    assert painel["agenda"]["proximo"].inicio.astimezone().hour == 11
    assert "recebimentos" not in painel and "financeiro" not in painel
    # Estimates show their totals (practitioners write them), but no money of the clinic.
    conteudo = resposta.content.decode()
    assert "Recebido hoje" not in conteudo and "Caixa do dia" not in conteudo


def test_listas_de_rechamadas_aniversariantes_e_orcamentos(cenario, cliente_de):
    painel = inicio(cenario, cliente_de, "recepcao").context["painel"]
    rechamadas = painel["rechamadas"]
    assert [r.data for r in rechamadas["lista"]] == [dia(1), HOJE]
    assert (rechamadas["total"], rechamadas["atrasadas"]) == (2, 1)
    assert [(p.nome, idade) for p, idade in painel["aniversariantes"]] == [("Maria Paciente", 41)]
    assert [o.validade for o in painel["orcamentos"]] == [dia(8)]


def test_concluir_rechamada_e_marcar_presenca_voltam_ao_inicio(cenario, cliente_de):
    cliente = cliente_de(cenario["recepcao"])
    painel = cliente.get(reverse("inicio")).context["painel"]
    rechamada = painel["rechamadas"]["lista"][0]
    resposta = cliente.post(
        reverse("rechamadas:concluir", args=[rechamada.pk]), {"next": reverse("inicio")}
    )
    assert resposta.url == reverse("inicio")
    proximo = painel["agenda"]["proximo"]
    resposta = cliente.post(
        reverse("agenda:situacao", args=[proximo.pk]), {"situacao": "compareceu"}, follow=True
    )
    assert "João Paciente compareceu." in resposta.content.decode()
    assert resposta.context["painel"]["agenda"]["compareceram"] == 2
    assert resposta.context["painel"]["rechamadas"]["total"] == 1


def test_sem_clinica_nao_ha_resumo(cenario, criar_usuario, cliente_de):
    resposta = cliente_de(criar_usuario("solto")).get(reverse("inicio"))
    assert "painel" not in resposta.context
    assert "não está vinculado a nenhuma clínica" in resposta.content.decode()


def test_saudacao_pela_hora(monkeypatch, criar_usuario, cliente_de):
    usuario = criar_usuario("maria")
    for hora, saudacao in [(7, "Bom dia"), (13, "Boa tarde"), (20, "Boa noite")]:
        momento = timezone.make_aware(datetime.datetime(2031, 3, 5, hora))
        monkeypatch.setattr(timezone, "now", lambda momento=momento: momento)
        # Logged in at the patched time, so the session is not seen as expired.
        conteudo = cliente_de(usuario).get(reverse("inicio")).content.decode()
        assert f"{saudacao}, maria" in conteudo
