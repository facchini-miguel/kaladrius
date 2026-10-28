"""Home page summary of the day (0.24.0).

Each block is built only when the user may see its module, so the front desk never gets
the clinic's expenses and a practitioner gets only their own schedule.
"""

import datetime

from django.db.models import Count, Sum
from django.utils import timezone

from apps.agenda import servicos as agenda
from apps.agenda.models import Agendamento
from apps.financeiro import servicos as financeiro
from apps.financeiro.models import ZERO, Caixa, Lancamento, Pagamento, Parcela
from apps.orcamentos.models import Orcamento
from apps.pacientes.models import Paciente
from apps.rechamadas.models import Rechamada

from .permissoes import Acao, Modulo, pode, so_a_propria_agenda

# How many lines each list shows before the "see all" link.
LIMITE = 8
# Estimates whose validity ends within this many days.
DIAS_ORCAMENTO = 7
DIAS_A_PAGAR = 7


def montar(request):
    hoje = timezone.localdate()
    painel = {"hoje": hoje}
    if pode(request, Modulo.AGENDA, Acao.VER):
        painel["agenda"] = _agenda(request, hoje)
    if pode(request, Modulo.RECHAMADAS, Acao.VER):
        painel["rechamadas"] = _rechamadas(hoje)
    if pode(request, Modulo.ANIVERSARIANTES, Acao.VER):
        painel["aniversariantes"] = _aniversariantes(hoje)
    if pode(request, Modulo.ORCAMENTOS, Acao.VER):
        painel["orcamentos"] = _orcamentos(hoje)
    if pode(request, Modulo.RECEBIMENTOS, Acao.VER):
        painel["recebimentos"] = _recebimentos(hoje)
    if pode(request, Modulo.FINANCEIRO, Acao.VER):
        painel["financeiro"] = _financeiro(hoje)
    return painel


def _agenda(request, hoje):
    agora = timezone.now()
    visiveis = agenda.agendamentos_visiveis(request)
    do_dia = list(
        visiveis.filter(inicio__date=hoje)
        .select_related("paciente", "profissional", "tipo")
        .order_by("inicio", "profissional__nome")
    )
    pacientes = [a for a in do_dia if a.paciente_id]
    situacao = Agendamento.Situacao
    contagem = {valor: 0 for valor in situacao.values}
    for agendamento in pacientes:
        contagem[agendamento.situacao] += 1
    pendentes = [a for a in pacientes if a.situacao == situacao.AGENDADO]
    # No-show rate of the month so far, over the appointments someone marked.
    marcados = dict(
        visiveis.filter(
            inicio__date__gte=hoje.replace(day=1),
            inicio__date__lte=hoje,
            situacao__in=[situacao.COMPARECEU, situacao.FALTOU],
        )
        .order_by()
        .values_list("situacao")
        .annotate(total=Count("pk"))
    )
    vieram, faltaram = marcados.get(situacao.COMPARECEU, 0), marcados.get(situacao.FALTOU, 0)
    return {
        "lista": do_dia,
        # A practitioner sees only their own schedule, so the column would repeat their name.
        "mostrar_profissional": not so_a_propria_agenda(request),
        "pacientes": len(pacientes) - contagem[situacao.DESMARCOU],
        "compareceram": contagem[situacao.COMPARECEU],
        "faltaram": contagem[situacao.FALTOU],
        "desmarcaram": contagem[situacao.DESMARCOU],
        "a_seguir": sum(1 for a in pendentes if a.inicio > agora),
        "sem_marcacao": sum(1 for a in pendentes if a.inicio <= agora),
        "proximo": next((a for a in pendentes if a.fim > agora), None),
        "agora": agora,
        "faltas_mes": round(100 * faltaram / (vieram + faltaram)) if vieram + faltaram else None,
        "marcados_mes": vieram + faltaram,
    }


def _rechamadas(hoje):
    pendentes = Rechamada.objects.filter(
        concluida=False, data__lte=hoje, paciente__arquivado=False
    ).select_related("paciente")
    return {
        "lista": list(pendentes.order_by("data", "paciente__nome")[:LIMITE]),
        "total": pendentes.count(),
        "atrasadas": pendentes.filter(data__lt=hoje).count(),
    }


def _aniversariantes(hoje):
    return [
        (paciente, hoje.year - paciente.data_nascimento.year)
        for paciente in Paciente.objects.filter(
            ativo=True,
            arquivado=False,
            data_nascimento__month=hoje.month,
            data_nascimento__day=hoje.day,
        ).order_by("nome")
    ]


def _orcamentos(hoje):
    return list(
        Orcamento.objects.filter(
            situacao=Orcamento.Situacao.ABERTO,
            validade__gte=hoje,
            validade__lte=hoje + datetime.timedelta(days=DIAS_ORCAMENTO),
            paciente__arquivado=False,
        )
        .select_related("paciente")
        .prefetch_related("itens")
        .order_by("validade", "paciente__nome")
    )


def _soma_dos_saldos(parcelas):
    saldos = list(parcelas.values_list("saldo", flat=True))
    return sum(saldos, start=ZERO), len(saldos)


def _recebimentos(hoje):
    recebidos = financeiro.pagamentos_validos().filter(
        data=hoje, parcela__lancamento__tipo=Lancamento.Tipo.RECEBER
    )
    formas = dict(Pagamento.Forma.choices)
    por_forma = [
        (formas.get(forma, forma), total)
        for forma, total in recebidos.order_by()
        .values_list("forma")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    ]
    a_receber, parcelas = _soma_dos_saldos(
        Parcela.objects.abertas().filter(lancamento__tipo=Lancamento.Tipo.RECEBER, vencimento=hoje)
    )
    return {
        "recebido": sum((total for _forma, total in por_forma), start=ZERO),
        "por_forma": por_forma,
        "a_receber": a_receber,
        "parcelas_a_receber": parcelas,
        "caixas": list(Caixa.objects.filter(fechado_em__isnull=True).select_related("conta")),
    }


def _financeiro(hoje):
    recebido_hoje, pago_hoje = financeiro.recebido_e_pago(hoje, hoje)
    inicio_mes = hoje.replace(day=1)
    recebido_mes, pago_mes = financeiro.recebido_e_pago(inicio_mes, hoje)
    # The same days of last month (up to its last day, for the 31st).
    fim_anterior = inicio_mes - datetime.timedelta(days=1)
    inicio_anterior = fim_anterior.replace(day=1)
    ate_anterior = inicio_anterior.replace(day=min(hoje.day, fim_anterior.day))
    recebido_anterior, pago_anterior = financeiro.recebido_e_pago(inicio_anterior, ate_anterior)
    abertas = Parcela.objects.abertas()
    vencido, parcelas_vencidas = _soma_dos_saldos(
        abertas.filter(lancamento__tipo=Lancamento.Tipo.RECEBER, vencimento__lt=hoje)
    )
    a_pagar, contas_a_pagar = _soma_dos_saldos(
        abertas.filter(
            lancamento__tipo=Lancamento.Tipo.PAGAR,
            vencimento__lte=hoje + datetime.timedelta(days=DIAS_A_PAGAR),
        )
    )
    return {
        "pago_hoje": pago_hoje,
        "resultado_hoje": recebido_hoje - pago_hoje,
        "recebido_mes": recebido_mes,
        "pago_mes": pago_mes,
        "resultado_mes": recebido_mes - pago_mes,
        "resultado_anterior": recebido_anterior - pago_anterior,
        "inicio_anterior": inicio_anterior,
        "ate_anterior": ate_anterior,
        "vencido": vencido,
        "parcelas_vencidas": parcelas_vencidas,
        "a_pagar": a_pagar,
        "contas_a_pagar": contas_a_pagar,
        "saldo_contas": sum(
            (saldo for _conta, saldo in financeiro.saldos_das_contas()), start=ZERO
        ),
    }
