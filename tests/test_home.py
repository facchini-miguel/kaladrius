"""Home page summary of the day (0.24.0)."""

import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import usar_clinica
from apps.core.models import Papel
from apps.estimates.models import Estimate
from apps.finance import services as financeiro
from apps.finance.models import CashRegister, Category, Entry, FinancialAccount
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.schedule import services as agenda
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db

# A Wednesday, 10:30 in the clinic's time zone.
HOJE = datetime.date(2031, 3, 5)
AGORA = timezone.make_aware(datetime.datetime(2031, 3, 5, 10, 30))


def dia(number, mes=3):
    return datetime.date(2031, mes, number)


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
        Practitioner.objects.filter(pk=ana.pk).update(user=usuarios["dra"])
        tipo = AppointmentType.objects.get(name="Cirurgia")
        maria = Patient.objects.create(
            name="Maria Paciente",
            data_nascimento=dia(5, 3).replace(year=1990),
            telefone_celular="11987654321",
        )
        joao = Patient.objects.create(name="João Paciente")
        arquivado = Patient.objects.create(
            name="Paciente Arquivado", arquivado=True, data_nascimento=dia(5).replace(year=1980)
        )

        def agendar(data, hora, practitioner=ana, patient=maria, situacao="agendado"):
            Appointment.objects.create(
                practitioner=practitioner,
                tipo=tipo,
                patient=patient,
                description="" if patient else "Bloqueado",
                situacao=situacao,
                inicio=agenda.momento(data, datetime.time(hora)),
                fim=agenda.momento(data, datetime.time(hora + 1)),
            )

        agendar(HOJE, 8, situacao="compareceu")
        agendar(HOJE, 9, situacao="faltou")
        agendar(HOJE, 10, practitioner=bruno, patient=joao)  # started, nobody marked it
        agendar(HOJE, 11)
        agendar(HOJE, 14, situacao="desmarcou")
        agendar(HOJE, 16, patient=None)
        agendar(dia(3), 9, situacao="compareceu")
        agendar(dia(4), 9, situacao="faltou")
        agendar(dia(27, 2), 9, situacao="faltou")  # last month: not in this month's rate

        for data, concluida, patient in [
            (HOJE, False, maria),
            (dia(1), False, maria),
            (dia(2), True, maria),
            (HOJE, False, arquivado),
            (dia(10), False, maria),
        ]:
            Recall.objects.create(
                patient=patient, data=data, description="Revisão", concluida=concluida
            )

        for patient, validade, situacao in [
            (maria, dia(8), Estimate.Situacao.ABERTO),
            (maria, dia(20), Estimate.Situacao.ABERTO),
            (maria, dia(6), Estimate.Situacao.APROVADO),
            (arquivado, dia(6), Estimate.Situacao.ABERTO),
            (maria, dia(4), Estimate.Situacao.ABERTO),
        ]:
            Estimate.objects.create(
                patient=patient, data=dia(1), validade=validade, situacao=situacao
            )

        caixa = FinancialAccount.objects.get(name="Caixa")
        receita = Category.objects.get(name="Tratamento")
        despesa = Category.objects.get(name="Outras despesas")

        def lancar(tipo, valor, parcelas, vencimento, categoria, **campos):
            lancamento = financeiro.criar_lancamento(
                clinic=clinica_a,
                tipo=tipo,
                description="Teste",
                categoria=categoria,
                valor_total=Decimal(valor),
                parcelas=parcelas,
                primeiro_vencimento=vencimento,
                user=usuarios["admin"],
                **campos,
            )
            return list(lancamento.parcelas.order_by("number"))

        def pagar(parcela, valor, data, forma="pix"):
            financeiro.receber(
                parcela,
                user=usuarios["admin"],
                valor=Decimal(valor),
                data=data,
                forma=forma,
                conta=caixa,
            )

        # Due 05/01, 05/02 (overdue) and today; the first one is paid today.
        primeira, _segunda, _terceira = lancar(
            Entry.Tipo.RECEBER, "300", 3, dia(5, 1), receita, patient=maria
        )
        pagar(primeira, "100", HOJE)
        [fevereiro] = lancar(Entry.Tipo.RECEBER, "200", 1, dia(3, 2), receita, patient=joao)
        pagar(fevereiro, "200", dia(3, 2), forma="dinheiro")
        [conta_de_luz] = lancar(Entry.Tipo.PAGAR, "50", 1, HOJE, despesa, pessoa="Luz")
        pagar(conta_de_luz, "50", HOJE)
        lancar(Entry.Tipo.PAGAR, "80", 1, dia(10), despesa, pessoa="Aluguel")
        lancar(Entry.Tipo.PAGAR, "999", 1, dia(20), despesa, pessoa="Longe")
        CashRegister.objects.create(
            conta=caixa, valor_abertura=Decimal("0"), aberto_por=usuarios["admin"]
        )
    return {"clinic": clinica_a, **usuarios}


def inicio(cenario, cliente_de, quem):
    return cliente_de(cenario[quem]).get(reverse("home"))


def test_recepcao_ve_o_dia_sem_as_despesas(cenario, cliente_de):
    resposta = inicio(cenario, cliente_de, "recepcao")
    painel = resposta.context["painel"]
    dia_ = painel["agenda"]
    assert len(dia_["lista"]) == 6 and dia_["mostrar_profissional"]
    assert (dia_["pacientes"], dia_["compareceram"], dia_["faltaram"]) == (4, 1, 1)
    assert (dia_["desmarcaram"], dia_["a_seguir"], dia_["sem_marcacao"]) == (1, 1, 1)
    assert dia_["proximo"].patient.name == "João Paciente"  # 10:00–11:00, still going on
    # Month so far: came 08:00 today and on the 3rd; missed 09:00 today and on the 4th.
    assert (dia_["faltas_mes"], dia_["marcados_mes"]) == (50, 4)

    recebimentos = painel["recebimentos"]
    assert recebimentos["recebido"] == Decimal("100")
    assert recebimentos["por_forma"] == [("Pix", Decimal("100"))]
    assert (recebimentos["a_receber"], recebimentos["parcelas_a_receber"]) == (Decimal("100"), 1)
    assert [caixa.conta.name for caixa in recebimentos["caixas"]] == ["Caixa"]
    assert "financeiro" not in painel

    conteudo = resposta.content.decode()
    assert "Bom dia, recepcao" in conteudo
    assert "Recebido hoje" in conteudo and "Pago hoje" not in conteudo
    assert "Saldo nas contas" not in conteudo
    assert reverse("schedule:status", args=[dia_["proximo"].pk]) in conteudo


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
    assert {a.practitioner.name for a in painel["agenda"]["lista"]} == {"Dra. Ana"}
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
    assert [(p.name, idade) for p, idade in painel["aniversariantes"]] == [("Maria Paciente", 41)]
    assert [o.validade for o in painel["orcamentos"]] == [dia(8)]


def test_concluir_rechamada_e_marcar_presenca_voltam_ao_inicio(cenario, cliente_de):
    cliente = cliente_de(cenario["recepcao"])
    painel = cliente.get(reverse("home")).context["painel"]
    rechamada = painel["rechamadas"]["lista"][0]
    resposta = cliente.post(
        reverse("recalls:complete", args=[rechamada.pk]), {"next": reverse("home")}
    )
    assert resposta.url == reverse("home")
    proximo = painel["agenda"]["proximo"]
    resposta = cliente.post(
        reverse("schedule:status", args=[proximo.pk]), {"situacao": "compareceu"}, follow=True
    )
    assert "João Paciente compareceu." in resposta.content.decode()
    assert resposta.context["painel"]["agenda"]["compareceram"] == 2
    assert resposta.context["painel"]["rechamadas"]["total"] == 1


def test_sem_clinica_nao_ha_resumo(cenario, criar_usuario, cliente_de):
    resposta = cliente_de(criar_usuario("solto")).get(reverse("home"))
    assert "painel" not in resposta.context
    assert "não tem acesso a nenhuma clínica ativa" in resposta.content.decode()


def test_saudacao_pela_hora(monkeypatch, criar_usuario, cliente_de):
    user = criar_usuario("maria")
    for hora, saudacao in [(7, "Bom dia"), (13, "Boa tarde"), (20, "Boa noite")]:
        momento = timezone.make_aware(datetime.datetime(2031, 3, 5, hora))
        monkeypatch.setattr(timezone, "now", lambda momento=momento: momento)
        # Logged in at the patched time, so the session is not seen as expired.
        conteudo = cliente_de(user).get(reverse("home")).content.decode()
        assert f"{saudacao}, maria" in conteudo
