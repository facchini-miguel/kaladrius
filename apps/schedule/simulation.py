"""Fake schedule and recalls around today, for test clinics (fake data, not security).

Used by seed_sample_data and by simulate_activity (for a clinic whose own data is
anonymized test data). Only active, non-archived patients and active practitioners take
part, and slots already taken are skipped, so the overlap constraint is never hit.
"""

import datetime

from django.utils import timezone

from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall

from .models import Appointment, AppointmentType
from .services import momento

MOTIVOS_RECHAMADA = ["Revisão de 6 meses", "Retorno pós-procedimento", "Limpeza", "Reavaliação"]


def _pacientes(clinic):
    return list(Patient.objects.filter(clinic=clinic, ativo=True, arquivado=False))


def simular_agendamentos(clinic, sorteio, semanas_antes=2, semanas_depois=4, ocupacao=0.6):
    """Fill about `ocupacao` of the free weekday slots around today. Returns how many."""
    profissionais = list(Practitioner.objects.filter(clinic=clinic, ativo=True))
    tipos = list(
        AppointmentType.objects.filter(clinic=clinic, ativo=True).exclude(
            nome__in=["Liberado", "Ocupado"]
        )
    )
    pacientes = _pacientes(clinic)
    if not (profissionais and tipos and pacientes):
        return 0
    passo = datetime.timedelta(minutes=clinic.agenda_intervalo)
    hoje = timezone.localdate()
    segunda = hoje - datetime.timedelta(days=hoje.weekday() + 7 * semanas_antes)
    dias = [
        segunda + datetime.timedelta(days=n) for n in range(7 * (semanas_antes + semanas_depois))
    ]
    ocupados = {}
    for practitioner_id, inicio, fim in Appointment.objects.filter(
        clinic=clinic,
        inicio__lt=momento(dias[-1], datetime.time(23, 59)),
        fim__gt=momento(dias[0], datetime.time(0)),
    ).values_list("practitioner_id", "inicio", "fim"):
        ocupados.setdefault(practitioner_id, []).append((inicio, fim))

    def livre(practitioner, inicio, fim):
        return all(fim <= a or inicio >= b for a, b in ocupados.get(practitioner.pk, []))

    novos = []
    for dia in dias:
        if dia.weekday() >= 5:
            continue
        for practitioner in profissionais:
            atual = momento(dia, clinic.agenda_inicio)
            fim_do_dia = momento(dia, clinic.agenda_fim)
            while atual < fim_do_dia:
                duracao = passo * sorteio.choice([1, 1, 2])
                fim = atual + duracao
                if (
                    fim > fim_do_dia
                    or sorteio.random() > ocupacao
                    or not livre(practitioner, atual, fim)
                ):
                    atual += passo
                    continue
                com_paciente = sorteio.random() < 0.9
                novos.append(
                    Appointment(
                        clinic=clinic,
                        practitioner=practitioner,
                        tipo=sorteio.choice(tipos),
                        patient=sorteio.choice(pacientes) if com_paciente else None,
                        descricao="" if com_paciente else "Horário bloqueado",
                        situacao=_situacao(sorteio, atual) if com_paciente else "agendado",
                        inicio=atual,
                        fim=fim,
                    )
                )
                atual = fim
    Appointment.objects.bulk_create(novos, batch_size=1000)
    return len(novos)


def _situacao(sorteio, inicio):
    """Past appointments: most patients came, some missed or cancelled (0.24.0)."""
    if inicio > timezone.now():
        return Appointment.Situacao.AGENDADO
    sorteado = sorteio.random()
    if sorteado < 0.82:
        return Appointment.Situacao.COMPARECEU
    if sorteado < 0.92:
        return Appointment.Situacao.FALTOU
    return Appointment.Situacao.DESMARCOU


def simular_rechamadas(clinic, sorteio, quantidade=80, dias_antes=30, dias_depois=60):
    """Recalls from `dias_antes` ago to `dias_depois` ahead; past ones mostly done."""
    pacientes = _pacientes(clinic)
    if not pacientes:
        return 0
    hoje = timezone.localdate()
    novas = []
    for _ in range(quantidade):
        data = hoje + datetime.timedelta(days=sorteio.randint(-dias_antes, dias_depois))
        novas.append(
            Recall(
                clinic=clinic,
                patient=sorteio.choice(pacientes),
                data=data,
                descricao=sorteio.choice(MOTIVOS_RECHAMADA),
                concluida=data < hoje and sorteio.random() < 0.7,
            )
        )
    Recall.objects.bulk_create(novas)
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


def simular_financeiro(clinic, sorteio, quantidade=60, user=None):
    """Fake receivables from 90 days ago to today, in 1 to 6 installments.

    Installments due in the past are mostly paid (some are left overdue, for the debtors
    report); the first one of some entries is paid on the spot.
    """
    from decimal import Decimal

    from apps.finance import services
    from apps.finance.models import Category, CostCenter, Entry, FinancialAccount, Payment

    pacientes = _pacientes(clinic)
    categorias = list(Category.objects.filter(clinic=clinic, tipo=Category.Tipo.RECEITA))
    contas = list(FinancialAccount.objects.filter(clinic=clinic, ativa=True))
    profissionais = list(Practitioner.objects.filter(clinic=clinic, ativo=True))
    if not (pacientes and categorias and contas):
        return 0, 0
    hoje = timezone.localdate()
    formas = [forma for forma, _rotulo in Payment.Forma.em_uso(clinic.pais)]
    # Two cost centers (decision 095): the care itself and the office.
    centros = {
        nome: CostCenter.objects.get_or_create(clinic=clinic, nome=nome)[0]
        for nome in ("Atendimento", "Administrativo")
    }
    criados = 0
    for _ in range(quantidade):
        data = hoje - datetime.timedelta(days=sorteio.randint(0, 90))
        lancamento = services.criar_lancamento(
            clinic=clinic,
            tipo=Entry.Tipo.RECEBER,
            patient=sorteio.choice(pacientes),
            descricao=sorteio.choice(DESCRICOES_FINANCEIRAS),
            categoria=sorteio.choice(categorias),
            centro_custo=centros["Atendimento"],
            practitioner=sorteio.choice(profissionais) if profissionais else None,
            valor_total=Decimal(sorteio.randrange(150, 3000, 10)),
            data=data,
            parcelas=sorteio.choice([1, 1, 2, 3, 4, 6]),
            primeiro_vencimento=data,
            user=user,
        )
        for parcela in lancamento.parcelas.all():
            if parcela.vencimento <= hoje and sorteio.random() < 0.8:
                services.receber(
                    parcela,
                    user=user,
                    valor=parcela.valor,
                    data=parcela.vencimento,
                    forma=sorteio.choice(formas),
                    conta=sorteio.choice(contas),
                )
        criados += 1
    return criados, _simular_despesas(clinic, sorteio, contas, user, centros)


# Fake payables: (supplier, description, category, amount, monthly repetitions or None).
DESPESAS_SIMULADAS = [
    ("Imobiliária Central", "Aluguel", "Aluguel", 3000, 6),
    ("Companhia de energia", "Água, luz e internet", "Água, luz e internet", 450, 6),
    ("Dental Suprimentos", "Material odontológico", "Material odontológico", 1350, None),
    ("Laboratório Sorriso", "Prótese", "Laboratório de prótese", 980, None),
    ("Contabilidade Ágil", "Honorários contábeis", "Outras despesas", 600, 6),
]


DESPESAS_DO_ATENDIMENTO = {"Material odontológico", "Laboratório de prótese"}


def _simular_despesas(clinic, sorteio, contas, user, centros):
    """Monthly bills from 2 months ago to 3 months ahead and a few purchases (mostly paid)."""
    from decimal import Decimal

    from apps.finance import payment_methods as metodos
    from apps.finance import services
    from apps.finance.models import Category, Entry, Supplier

    # Bills are paid the way the clinic's country pays them (decision 123).
    do_pais = metodos.do_pais(clinic.pais).codigos
    contas_a_pagar = (metodos.PIX, metodos.BOLETO, metodos.TRANSFERENCIA, metodos.DEBITO_AUTOMATICO)
    formas = [forma for forma in contas_a_pagar if forma in do_pais]
    categorias = {
        c.nome: c for c in Category.objects.filter(clinic=clinic, tipo=Category.Tipo.DESPESA)
    }
    hoje = timezone.localdate()
    inicio = services.somar_meses(hoje.replace(day=10), -2)
    criadas = 0
    for fornecedor, descricao, categoria, valor, meses in DESPESAS_SIMULADAS:
        if categoria not in categorias:
            continue
        parcelas = meses or sorteio.choice([1, 2, 3])
        valor = Decimal(valor)
        cadastro, _criado = Supplier.objects.get_or_create(clinic=clinic, nome=fornecedor)
        lancamento = services.criar_lancamento(
            clinic=clinic,
            tipo=Entry.Tipo.PAGAR,
            fornecedor=cadastro,
            pessoa=fornecedor,
            descricao=descricao,
            categoria=categorias[categoria],
            centro_custo=centros[
                "Atendimento" if categoria in DESPESAS_DO_ATENDIMENTO else "Administrativo"
            ],
            valor_total=valor * parcelas if meses else valor,
            data=inicio,
            parcelas=parcelas,
            primeiro_vencimento=inicio if meses else hoje - datetime.timedelta(days=20),
            user=user,
        )
        for parcela in lancamento.parcelas.all():
            if parcela.vencimento <= hoje and sorteio.random() < 0.9:
                services.receber(
                    parcela,
                    user=user,
                    valor=parcela.valor,
                    data=parcela.vencimento,
                    forma=sorteio.choice(formas),
                    conta=sorteio.choice(contas),
                )
        criadas += 1
    return criadas


# Example price list for a test clinic without one: (name, price).
PROCEDIMENTOS_EXEMPLO = [
    ("Consulta de avaliação", 150),
    ("Limpeza (profilaxia)", 200),
    ("Restauração em resina", 250),
    ("Extração simples", 300),
    ("Tratamento de canal", 1200),
    ("Clareamento", 900),
    ("Coroa de porcelana", 1800),
    ("Aplicação de flúor", 80),
]


def simular_orcamentos(clinic, sorteio, quantidade=20, user=None):
    """Fake estimates of the last 60 days: some approved (they become receivables), some
    refused, the rest open. Creates an example price list if the clinic has none."""
    from decimal import Decimal

    from apps.dentistry.teeth import DENTES_PERMANENTES
    from apps.estimates import services
    from apps.estimates.models import (
        Estimate,
        EstimateItem,
        Procedure,
    )
    from apps.finance.models import Category

    tratamento = Category.objects.filter(clinic=clinic, nome="Tratamento").first()
    if not Procedure.objects.filter(clinic=clinic).exists():
        Procedure.objects.bulk_create(
            Procedure(clinic=clinic, nome=nome, valor=Decimal(valor), categoria=tratamento)
            for nome, valor in PROCEDIMENTOS_EXEMPLO
        )
    procedimentos = list(Procedure.objects.filter(clinic=clinic, ativo=True))
    pacientes = _pacientes(clinic)
    profissionais = list(Practitioner.objects.filter(clinic=clinic, ativo=True))
    categoria = (
        tratamento or Category.objects.filter(clinic=clinic, tipo=Category.Tipo.RECEITA).first()
    )
    if not (procedimentos and pacientes and categoria):
        return 0
    dentes = [d for linha in DENTES_PERMANENTES for d in linha]
    hoje = timezone.localdate()
    for _ in range(quantidade):
        data = hoje - datetime.timedelta(days=sorteio.randint(0, 60))
        orcamento = Estimate.objects.create(
            clinic=clinic,
            patient=sorteio.choice(pacientes),
            practitioner=sorteio.choice(profissionais) if profissionais else None,
            data=data,
            validade=data + datetime.timedelta(days=30),
            created_by=user,
        )
        for procedimento in sorteio.sample(procedimentos, sorteio.randint(1, 3)):
            escolhidos = sorted(sorteio.sample(dentes, sorteio.randint(0, 3)))
            EstimateItem.objects.create(
                clinic=clinic,
                orcamento=orcamento,
                procedimento=procedimento,
                descricao=procedimento.nome,
                dentes=",".join(str(d) for d in escolhidos),
                quantidade=max(len(escolhidos), 1),
                valor_unitario=procedimento.valor,
            )
        sorte = sorteio.random()
        if sorte < 0.4:
            services.aprovar(
                orcamento,
                parcelas=sorteio.choice([1, 2, 3, 4]),
                primeiro_vencimento=data + datetime.timedelta(days=7),
                categoria=categoria,
                user=user,
            )
        elif sorte < 0.6:
            services.recusar(orcamento, user=user)
    return quantidade


def simular_comissoes(clinic, sorteio, user=None):
    """Give practitioners without one a commission percentage and pay out what each had
    pending up to the end of last month (test clinics only). Returns how many were paid."""
    from decimal import Decimal

    from apps.finance import commissions
    from apps.finance.models import Category

    categoria = Category.objects.filter(
        clinic=clinic, tipo=Category.Tipo.DESPESA, nome="Comissões"
    ).first()
    if categoria is None:
        return 0
    fim_do_mes_passado = timezone.localdate().replace(day=1) - datetime.timedelta(days=1)
    pagas = 0
    for practitioner in Practitioner.objects.filter(clinic=clinic, ativo=True):
        if not practitioner.comissao_percentual:
            practitioner.comissao_percentual = Decimal(sorteio.choice([30, 35, 40]))
            practitioner.save(update_fields=["comissao_percentual"])
        # Runs without isolation (like the command); the practitioner pins the clinic.
        if commissions.pendente(practitioner, fim_do_mes_passado)["valor"] > 0:
            commissions.pagar(
                practitioner,
                ate=fim_do_mes_passado,
                vencimento=fim_do_mes_passado + datetime.timedelta(days=5),
                categoria=categoria,
                user=user,
            )
            pagas += 1
    return pagas
