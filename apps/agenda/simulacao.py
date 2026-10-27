"""Fake schedule and recalls around today, for test clinics (fake data, not security).

Used by popular_dados_teste and by simular_movimento (for a clinic whose own data is
anonymized test data). Only active, non-archived patients and active practitioners take
part, and slots already taken are skipped, so the overlap constraint is never hit.
"""

import datetime

from django.utils import timezone

from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada

from .models import Agendamento, TipoAtendimento
from .servicos import momento

MOTIVOS_RECHAMADA = ["Revisão de 6 meses", "Retorno pós-procedimento", "Limpeza", "Reavaliação"]


def _pacientes(clinica):
    return list(Paciente.objects.filter(clinica=clinica, ativo=True, arquivado=False))


def simular_agendamentos(clinica, sorteio, semanas_antes=2, semanas_depois=4, ocupacao=0.6):
    """Fill about `ocupacao` of the free weekday slots around today. Returns how many."""
    profissionais = list(Profissional.objects.filter(clinica=clinica, ativo=True))
    tipos = list(
        TipoAtendimento.objects.filter(clinica=clinica, ativo=True).exclude(
            nome__in=["Liberado", "Ocupado"]
        )
    )
    pacientes = _pacientes(clinica)
    if not (profissionais and tipos and pacientes):
        return 0
    passo = datetime.timedelta(minutes=clinica.agenda_intervalo)
    hoje = timezone.localdate()
    segunda = hoje - datetime.timedelta(days=hoje.weekday() + 7 * semanas_antes)
    dias = [
        segunda + datetime.timedelta(days=n) for n in range(7 * (semanas_antes + semanas_depois))
    ]
    ocupados = {}
    for profissional_id, inicio, fim in Agendamento.objects.filter(
        clinica=clinica,
        inicio__lt=momento(dias[-1], datetime.time(23, 59)),
        fim__gt=momento(dias[0], datetime.time(0)),
    ).values_list("profissional_id", "inicio", "fim"):
        ocupados.setdefault(profissional_id, []).append((inicio, fim))

    def livre(profissional, inicio, fim):
        return all(fim <= a or inicio >= b for a, b in ocupados.get(profissional.pk, []))

    novos = []
    for dia in dias:
        if dia.weekday() >= 5:
            continue
        for profissional in profissionais:
            atual = momento(dia, clinica.agenda_inicio)
            fim_do_dia = momento(dia, clinica.agenda_fim)
            while atual < fim_do_dia:
                duracao = passo * sorteio.choice([1, 1, 2])
                fim = atual + duracao
                if (
                    fim > fim_do_dia
                    or sorteio.random() > ocupacao
                    or not livre(profissional, atual, fim)
                ):
                    atual += passo
                    continue
                com_paciente = sorteio.random() < 0.9
                novos.append(
                    Agendamento(
                        clinica=clinica,
                        profissional=profissional,
                        tipo=sorteio.choice(tipos),
                        paciente=sorteio.choice(pacientes) if com_paciente else None,
                        descricao="" if com_paciente else "Horário bloqueado",
                        inicio=atual,
                        fim=fim,
                    )
                )
                atual = fim
    Agendamento.objects.bulk_create(novos, batch_size=1000)
    return len(novos)


def simular_rechamadas(clinica, sorteio, quantidade=80, dias_antes=30, dias_depois=60):
    """Recalls from `dias_antes` ago to `dias_depois` ahead; past ones mostly done."""
    pacientes = _pacientes(clinica)
    if not pacientes:
        return 0
    hoje = timezone.localdate()
    novas = []
    for _ in range(quantidade):
        data = hoje + datetime.timedelta(days=sorteio.randint(-dias_antes, dias_depois))
        novas.append(
            Rechamada(
                clinica=clinica,
                paciente=sorteio.choice(pacientes),
                data=data,
                descricao=sorteio.choice(MOTIVOS_RECHAMADA),
                concluida=data < hoje and sorteio.random() < 0.7,
            )
        )
    Rechamada.objects.bulk_create(novas)
    return len(novas)


DESCRICOES_FINANCEIRAS = [
    "Limpeza",
    "Restauração",
    "Tratamento de canal",
    "Prótese",
    "Clareamento",
    "Aparelho ortodôntico",
    "Extração",
    "Consulta",
]


def simular_financeiro(clinica, sorteio, quantidade=60, usuario=None):
    """Fake receivables from 90 days ago to today, in 1 to 6 installments.

    Installments due in the past are mostly paid (some are left overdue, for the debtors
    report); the first one of some entries is paid on the spot.
    """
    from decimal import Decimal

    from apps.financeiro import servicos
    from apps.financeiro.models import Categoria, Conta, Lancamento, Pagamento

    pacientes = _pacientes(clinica)
    categorias = list(Categoria.objects.filter(clinica=clinica, tipo=Categoria.Tipo.RECEITA))
    contas = list(Conta.objects.filter(clinica=clinica, ativa=True))
    profissionais = list(Profissional.objects.filter(clinica=clinica, ativo=True))
    if not (pacientes and categorias and contas):
        return 0
    hoje = timezone.localdate()
    formas = [forma for forma, _rotulo in Pagamento.Forma.choices]
    criados = 0
    for _ in range(quantidade):
        data = hoje - datetime.timedelta(days=sorteio.randint(0, 90))
        lancamento = servicos.criar_lancamento(
            clinica=clinica,
            tipo=Lancamento.Tipo.RECEBER,
            paciente=sorteio.choice(pacientes),
            descricao=sorteio.choice(DESCRICOES_FINANCEIRAS),
            categoria=sorteio.choice(categorias),
            profissional=sorteio.choice(profissionais) if profissionais else None,
            valor_total=Decimal(sorteio.randrange(150, 3000, 10)),
            data=data,
            parcelas=sorteio.choice([1, 1, 2, 3, 4, 6]),
            primeiro_vencimento=data,
            usuario=usuario,
        )
        for parcela in lancamento.parcelas.all():
            if parcela.vencimento <= hoje and sorteio.random() < 0.8:
                servicos.receber(
                    parcela,
                    usuario=usuario,
                    valor=parcela.valor,
                    data=parcela.vencimento,
                    forma=sorteio.choice(formas),
                    conta=sorteio.choice(contas),
                )
        criados += 1
    return criados
