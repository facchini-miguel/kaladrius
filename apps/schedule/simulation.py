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
from .services import timestamp

MOTIVOS_RECHAMADA = ["Revisão de 6 meses", "Retorno pós-procedimento", "Limpeza", "Reavaliação"]


def _pacientes(clinic):
    return list(Patient.objects.filter(clinic=clinic, active=True, archived=False))


def simular_agendamentos(clinic, sorteio, semanas_antes=2, semanas_depois=4, ocupacao=0.6):
    """Fill about `ocupacao` of the free weekday slots around today. Returns how many."""
    profissionais = list(Practitioner.objects.filter(clinic=clinic, active=True))
    tipos = list(
        AppointmentType.objects.filter(clinic=clinic, active=True).exclude(
            name__in=["Liberado", "Ocupado"]
        )
    )
    pacientes = _pacientes(clinic)
    if not (profissionais and tipos and pacientes):
        return 0
    passo = datetime.timedelta(minutes=clinic.schedule_interval)
    today = timezone.localdate()
    segunda = today - datetime.timedelta(days=today.weekday() + 7 * semanas_antes)
    days = [
        segunda + datetime.timedelta(days=n) for n in range(7 * (semanas_antes + semanas_depois))
    ]
    ocupados = {}
    for practitioner_id, start, end in Appointment.objects.filter(
        clinic=clinic,
        start__lt=timestamp(days[-1], datetime.time(23, 59)),
        end__gt=timestamp(days[0], datetime.time(0)),
    ).values_list("practitioner_id", "start", "end"):
        ocupados.setdefault(practitioner_id, []).append((start, end))

    def livre(practitioner, start, end):
        return all(end <= a or start >= b for a, b in ocupados.get(practitioner.pk, []))

    novos = []
    for day in days:
        if day.weekday() >= 5:
            continue
        for practitioner in profissionais:
            current = timestamp(day, clinic.schedule_start)
            fim_do_dia = timestamp(day, clinic.schedule_end)
            while current < fim_do_dia:
                duration = passo * sorteio.choice([1, 1, 2])
                end = current + duration
                if (
                    end > fim_do_dia
                    or sorteio.random() > ocupacao
                    or not livre(practitioner, current, end)
                ):
                    current += passo
                    continue
                com_paciente = sorteio.random() < 0.9
                novos.append(
                    Appointment(
                        clinic=clinic,
                        practitioner=practitioner,
                        kind=sorteio.choice(tipos),
                        patient=sorteio.choice(pacientes) if com_paciente else None,
                        description="" if com_paciente else "Horário bloqueado",
                        status=_situacao(sorteio, current) if com_paciente else "agendado",
                        start=current,
                        end=end,
                    )
                )
                current = end
    Appointment.objects.bulk_create(novos, batch_size=1000)
    return len(novos)


def _situacao(sorteio, start):
    """Past appointments: most patients came, some missed or cancelled (0.24.0)."""
    if start > timezone.now():
        return Appointment.Situacao.AGENDADO
    sorteado = sorteio.random()
    if sorteado < 0.82:
        return Appointment.Situacao.COMPARECEU
    if sorteado < 0.92:
        return Appointment.Situacao.FALTOU
    return Appointment.Situacao.DESMARCOU


def simular_rechamadas(clinic, sorteio, quantity=80, dias_antes=30, dias_depois=60):
    """Recalls from `dias_antes` ago to `dias_depois` ahead; past ones mostly done."""
    pacientes = _pacientes(clinic)
    if not pacientes:
        return 0
    today = timezone.localdate()
    novas = []
    for _ in range(quantity):
        date = today + datetime.timedelta(days=sorteio.randint(-dias_antes, dias_depois))
        novas.append(
            Recall(
                clinic=clinic,
                patient=sorteio.choice(pacientes),
                date=date,
                description=sorteio.choice(MOTIVOS_RECHAMADA),
                done=date < today and sorteio.random() < 0.7,
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


def simular_financeiro(clinic, sorteio, quantity=60, user=None):
    """Fake receivables from 90 days ago to today, in 1 to 6 installments.

    Installments due in the past are mostly paid (some are left overdue, for the debtors
    report); the first one of some entries is paid on the spot.
    """
    from decimal import Decimal

    from apps.finance import services
    from apps.finance.models import Category, CostCenter, Entry, FinancialAccount, Payment

    pacientes = _pacientes(clinic)
    categorias = list(Category.objects.filter(clinic=clinic, kind=Category.Tipo.RECEITA))
    contas = list(FinancialAccount.objects.filter(clinic=clinic, active=True))
    profissionais = list(Practitioner.objects.filter(clinic=clinic, active=True))
    if not (pacientes and categorias and contas):
        return 0, 0
    today = timezone.localdate()
    formas = [method for method, _rotulo in Payment.Forma.em_uso(clinic.country)]
    # Two cost centers (decision 095): the care itself and the office.
    centros = {
        name: CostCenter.objects.get_or_create(clinic=clinic, name=name)[0]
        for name in ("Atendimento", "Administrativo")
    }
    criados = 0
    for _ in range(quantity):
        date = today - datetime.timedelta(days=sorteio.randint(0, 90))
        entry = services.criar_lancamento(
            clinic=clinic,
            kind=Entry.Tipo.RECEBER,
            patient=sorteio.choice(pacientes),
            description=sorteio.choice(DESCRICOES_FINANCEIRAS),
            category=sorteio.choice(categorias),
            cost_center=centros["Atendimento"],
            practitioner=sorteio.choice(profissionais) if profissionais else None,
            total_amount=Decimal(sorteio.randrange(150, 3000, 10)),
            date=date,
            parcelas=sorteio.choice([1, 1, 2, 3, 4, 6]),
            primeiro_vencimento=date,
            user=user,
        )
        for installment in entry.parcelas.all():
            if installment.due_date <= today and sorteio.random() < 0.8:
                services.receber(
                    installment,
                    user=user,
                    amount=installment.amount,
                    date=installment.due_date,
                    method=sorteio.choice(formas),
                    account=sorteio.choice(contas),
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
    do_pais = metodos.do_pais(clinic.country).codigos
    contas_a_pagar = (metodos.PIX, metodos.BOLETO, metodos.TRANSFERENCIA, metodos.DEBITO_AUTOMATICO)
    formas = [method for method in contas_a_pagar if method in do_pais]
    categorias = {
        c.name: c for c in Category.objects.filter(clinic=clinic, kind=Category.Tipo.DESPESA)
    }
    today = timezone.localdate()
    start = services.somar_meses(today.replace(day=10), -2)
    criadas = 0
    for supplier, description, category, amount, meses in DESPESAS_SIMULADAS:
        if category not in categorias:
            continue
        parcelas = meses or sorteio.choice([1, 2, 3])
        amount = Decimal(amount)
        cadastro, _criado = Supplier.objects.get_or_create(clinic=clinic, name=supplier)
        entry = services.criar_lancamento(
            clinic=clinic,
            kind=Entry.Tipo.PAGAR,
            supplier=cadastro,
            payer=supplier,
            description=description,
            category=categorias[category],
            cost_center=centros[
                "Atendimento" if category in DESPESAS_DO_ATENDIMENTO else "Administrativo"
            ],
            total_amount=amount * parcelas if meses else amount,
            date=start,
            parcelas=parcelas,
            primeiro_vencimento=start if meses else today - datetime.timedelta(days=20),
            user=user,
        )
        for installment in entry.parcelas.all():
            if installment.due_date <= today and sorteio.random() < 0.9:
                services.receber(
                    installment,
                    user=user,
                    amount=installment.amount,
                    date=installment.due_date,
                    method=sorteio.choice(formas),
                    account=sorteio.choice(contas),
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


def simular_orcamentos(clinic, sorteio, quantity=20, user=None):
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

    tratamento = Category.objects.filter(clinic=clinic, name="Tratamento").first()
    if not Procedure.objects.filter(clinic=clinic).exists():
        Procedure.objects.bulk_create(
            Procedure(clinic=clinic, name=name, amount=Decimal(amount), category=tratamento)
            for name, amount in PROCEDIMENTOS_EXEMPLO
        )
    procedimentos = list(Procedure.objects.filter(clinic=clinic, active=True))
    pacientes = _pacientes(clinic)
    profissionais = list(Practitioner.objects.filter(clinic=clinic, active=True))
    category = (
        tratamento or Category.objects.filter(clinic=clinic, kind=Category.Tipo.RECEITA).first()
    )
    if not (procedimentos and pacientes and category):
        return 0
    teeth = [d for row in DENTES_PERMANENTES for d in row]
    today = timezone.localdate()
    for _ in range(quantity):
        date = today - datetime.timedelta(days=sorteio.randint(0, 60))
        estimate = Estimate.objects.create(
            clinic=clinic,
            patient=sorteio.choice(pacientes),
            practitioner=sorteio.choice(profissionais) if profissionais else None,
            date=date,
            valid_until=date + datetime.timedelta(days=30),
            created_by=user,
        )
        for procedure in sorteio.sample(procedimentos, sorteio.randint(1, 3)):
            escolhidos = sorted(sorteio.sample(teeth, sorteio.randint(0, 3)))
            EstimateItem.objects.create(
                clinic=clinic,
                estimate=estimate,
                procedure=procedure,
                description=procedure.name,
                teeth=",".join(str(d) for d in escolhidos),
                quantity=max(len(escolhidos), 1),
                unit_price=procedure.amount,
            )
        sorte = sorteio.random()
        if sorte < 0.4:
            services.aprovar(
                estimate,
                parcelas=sorteio.choice([1, 2, 3, 4]),
                primeiro_vencimento=date + datetime.timedelta(days=7),
                category=category,
                user=user,
            )
        elif sorte < 0.6:
            services.recusar(estimate, user=user)
    return quantity


def simular_comissoes(clinic, sorteio, user=None):
    """Give practitioners without one a commission percentage and pay out what each had
    pending up to the end of last month (test clinics only). Returns how many were paid."""
    from decimal import Decimal

    from apps.finance import commissions
    from apps.finance.models import Category

    category = Category.objects.filter(
        clinic=clinic, kind=Category.Tipo.DESPESA, name="Comissões"
    ).first()
    if category is None:
        return 0
    fim_do_mes_passado = timezone.localdate().replace(day=1) - datetime.timedelta(days=1)
    pagas = 0
    for practitioner in Practitioner.objects.filter(clinic=clinic, active=True):
        if not practitioner.commission_percentage:
            practitioner.commission_percentage = Decimal(sorteio.choice([30, 35, 40]))
            practitioner.save(update_fields=["commission_percentage"])
        # Runs without isolation (like the command); the practitioner pins the clinic.
        if commissions.pendente(practitioner, fim_do_mes_passado)["amount"] > 0:
            commissions.pagar(
                practitioner,
                until=fim_do_mes_passado,
                due_date=fim_do_mes_passado + datetime.timedelta(days=5),
                category=category,
                user=user,
            )
            pagas += 1
    return pagas
