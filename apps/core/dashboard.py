"""Home page summary of the day (0.24.0).

Each block is built only when the user may see its module, so the front desk never gets
the clinic's expenses and a practitioner gets only their own schedule.
"""

import datetime

from django.db.models import Count, Sum
from django.utils import timezone

from apps.estimates.models import Estimate
from apps.finance import services as financeiro
from apps.finance.models import ZERO, CashRegister, Entry, Installment
from apps.finance.payment_methods import rotulos as rotulos_das_formas
from apps.patients.models import Patient
from apps.recalls.models import Recall
from apps.schedule import services as agenda
from apps.schedule.models import Appointment

from .permissions import Acao, Modulo, pode, so_a_propria_agenda

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
        visiveis.filter(start__date=hoje)
        .select_related("patient", "practitioner", "kind")
        .order_by("start", "practitioner__name")
    )
    pacientes = [a for a in do_dia if a.patient_id]
    status = Appointment.Situacao
    contagem = {value: 0 for value in status.values}
    for agendamento in pacientes:
        contagem[agendamento.status] += 1
    pendentes = [a for a in pacientes if a.status == status.AGENDADO]
    # No-show rate of the month so far, over the appointments someone marked.
    marcados = dict(
        visiveis.filter(
            start__date__gte=hoje.replace(day=1),
            start__date__lte=hoje,
            status__in=[status.COMPARECEU, status.FALTOU],
        )
        .order_by()
        .values_list("status")
        .annotate(total=Count("pk"))
    )
    vieram, faltaram = marcados.get(status.COMPARECEU, 0), marcados.get(status.FALTOU, 0)
    return {
        "lista": do_dia,
        # A practitioner sees only their own schedule, so the column would repeat their name.
        "mostrar_profissional": not so_a_propria_agenda(request),
        "pacientes": len(pacientes) - contagem[status.DESMARCOU],
        "compareceram": contagem[status.COMPARECEU],
        "faltaram": contagem[status.FALTOU],
        "desmarcaram": contagem[status.DESMARCOU],
        "a_seguir": sum(1 for a in pendentes if a.start > agora),
        "sem_marcacao": sum(1 for a in pendentes if a.start <= agora),
        "proximo": next((a for a in pendentes if a.end > agora), None),
        "agora": agora,
        "faltas_mes": round(100 * faltaram / (vieram + faltaram)) if vieram + faltaram else None,
        "marcados_mes": vieram + faltaram,
    }


def _rechamadas(hoje):
    pendentes = Recall.objects.filter(
        concluida=False, date__lte=hoje, patient__arquivado=False
    ).select_related("patient")
    return {
        "lista": list(pendentes.order_by("date", "patient__name")[:LIMITE]),
        "total": pendentes.count(),
        "atrasadas": pendentes.filter(date__lt=hoje).count(),
    }


def _aniversariantes(hoje):
    return [
        (patient, hoje.year - patient.data_nascimento.year)
        for patient in Patient.objects.filter(
            active=True,
            arquivado=False,
            data_nascimento__month=hoje.month,
            data_nascimento__day=hoje.day,
        ).order_by("name")
    ]


def _orcamentos(hoje):
    return list(
        Estimate.objects.filter(
            status=Estimate.Situacao.ABERTO,
            valid_until__gte=hoje,
            valid_until__lte=hoje + datetime.timedelta(days=DIAS_ORCAMENTO),
            patient__arquivado=False,
        )
        .select_related("patient")
        .prefetch_related("itens")
        .order_by("valid_until", "patient__name")
    )


def _soma_dos_saldos(parcelas):
    saldos = list(parcelas.values_list("balance", flat=True))
    return sum(saldos, start=ZERO), len(saldos)


def _recebimentos(hoje):
    recebidos = financeiro.pagamentos_validos().filter(
        date=hoje, installment__entry__kind=Entry.Tipo.RECEBER
    )
    formas = rotulos_das_formas()
    por_forma = [
        (formas.get(method, method), total)
        for method, total in recebidos.order_by()
        .values_list("method")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    ]
    a_receber, parcelas = _soma_dos_saldos(
        Installment.objects.abertas().filter(entry__kind=Entry.Tipo.RECEBER, due_date=hoje)
    )
    return {
        "recebido": sum((total for _forma, total in por_forma), start=ZERO),
        "por_forma": por_forma,
        "a_receber": a_receber,
        "parcelas_a_receber": parcelas,
        "caixas": list(
            CashRegister.objects.filter(closed_at__isnull=True).select_related("account")
        ),
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
    abertas = Installment.objects.abertas()
    vencido, parcelas_vencidas = _soma_dos_saldos(
        abertas.filter(entry__kind=Entry.Tipo.RECEBER, due_date__lt=hoje)
    )
    a_pagar, contas_a_pagar = _soma_dos_saldos(
        abertas.filter(
            entry__kind=Entry.Tipo.PAGAR,
            due_date__lte=hoje + datetime.timedelta(days=DIAS_A_PAGAR),
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
