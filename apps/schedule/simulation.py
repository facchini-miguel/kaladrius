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

RECALL_REASONS = ["Revisão de 6 meses", "Retorno pós-procedimento", "Limpeza", "Reavaliação"]


def _patients(clinic):
    return list(Patient.objects.filter(clinic=clinic, active=True, archived=False))


def simulate_appointments(clinic, rng, weeks_before=2, weeks_after=4, occupancy=0.6):
    """Fill about `ocupacao` of the free weekday slots around today. Returns how many."""
    practitioners = list(Practitioner.objects.filter(clinic=clinic, active=True))
    appointment_types = list(
        AppointmentType.objects.filter(clinic=clinic, active=True).exclude(
            name__in=["Liberado", "Ocupado"]
        )
    )
    patients = _patients(clinic)
    if not (practitioners and appointment_types and patients):
        return 0
    step = datetime.timedelta(minutes=clinic.schedule_interval)
    today = timezone.localdate()
    second = today - datetime.timedelta(days=today.weekday() + 7 * weeks_before)
    days = [second + datetime.timedelta(days=n) for n in range(7 * (weeks_before + weeks_after))]
    busy_slots = {}
    for practitioner_id, start, end in Appointment.objects.filter(
        clinic=clinic,
        start__lt=timestamp(days[-1], datetime.time(23, 59)),
        end__gt=timestamp(days[0], datetime.time(0)),
    ).values_list("practitioner_id", "start", "end"):
        busy_slots.setdefault(practitioner_id, []).append((start, end))

    def free(practitioner, start, end):
        return all(end <= a or start >= b for a, b in busy_slots.get(practitioner.pk, []))

    new_ones = []
    for day in days:
        if day.weekday() >= 5:
            continue
        for practitioner in practitioners:
            current = timestamp(day, clinic.schedule_start)
            end_of_day = timestamp(day, clinic.schedule_end)
            while current < end_of_day:
                duration = step * rng.choice([1, 1, 2])
                end = current + duration
                if (
                    end > end_of_day
                    or rng.random() > occupancy
                    or not free(practitioner, current, end)
                ):
                    current += step
                    continue
                with_patient = rng.random() < 0.9
                new_ones.append(
                    Appointment(
                        clinic=clinic,
                        practitioner=practitioner,
                        kind=rng.choice(appointment_types),
                        patient=rng.choice(patients) if with_patient else None,
                        description="" if with_patient else "Horário bloqueado",
                        status=_status(rng, current) if with_patient else "agendado",
                        start=current,
                        end=end,
                    )
                )
                current = end
    Appointment.objects.bulk_create(new_ones, batch_size=1000)
    return len(new_ones)


def _status(rng, start):
    """Past appointments: most patients came, some missed or cancelled (0.24.0)."""
    if start > timezone.now():
        return Appointment.Status.BOOKED
    drawn = rng.random()
    if drawn < 0.82:
        return Appointment.Status.ATTENDED
    if drawn < 0.92:
        return Appointment.Status.MISSED
    return Appointment.Status.CANCELLED


def simulate_recalls(clinic, rng, quantity=80, days_before=30, days_after=60):
    """Recalls from `dias_antes` ago to `dias_depois` ahead; past ones mostly done."""
    patients = _patients(clinic)
    if not patients:
        return 0
    today = timezone.localdate()
    novas = []
    for _ in range(quantity):
        date = today + datetime.timedelta(days=rng.randint(-days_before, days_after))
        novas.append(
            Recall(
                clinic=clinic,
                patient=rng.choice(patients),
                date=date,
                description=rng.choice(RECALL_REASONS),
                done=date < today and rng.random() < 0.7,
            )
        )
    Recall.objects.bulk_create(novas)
    return len(novas)


FINANCE_DESCRIPTIONS = [
    "Limpeza",
    "Restauração",
    "Tratamento de canal",
    "Prótese",
    "Clareamento",
    "Aparelho ortodôntico",
    "Extração",
    "Consulta",
]


def simulate_finance(clinic, rng, quantity=60, user=None):
    """Fake receivables from 90 days ago to today, in 1 to 6 installments.

    Installments due in the past are mostly paid (some are left overdue, for the debtors
    report); the first one of some entries is paid on the spot.
    """
    from decimal import Decimal

    from apps.finance import services
    from apps.finance.models import Category, CostCenter, Entry, FinancialAccount, Payment

    patients = _patients(clinic)
    categories = list(Category.objects.filter(clinic=clinic, kind=Category.Kind.INCOME))
    accounts = list(FinancialAccount.objects.filter(clinic=clinic, active=True))
    practitioners = list(Practitioner.objects.filter(clinic=clinic, active=True))
    if not (patients and categories and accounts):
        return 0, 0
    today = timezone.localdate()
    methods = [method for method, _label in Payment.Method.in_use(clinic.country)]
    # Two cost centers (decision 095): the care itself and the office.
    cost_centers = {
        name: CostCenter.objects.get_or_create(clinic=clinic, name=name)[0]
        for name in ("Atendimento", "Administrativo")
    }
    created_count = 0
    for _ in range(quantity):
        date = today - datetime.timedelta(days=rng.randint(0, 90))
        entry = services.create_entry(
            clinic=clinic,
            kind=Entry.Kind.RECEIVABLE,
            patient=rng.choice(patients),
            description=rng.choice(FINANCE_DESCRIPTIONS),
            category=rng.choice(categories),
            cost_center=cost_centers["Atendimento"],
            practitioner=rng.choice(practitioners) if practitioners else None,
            total_amount=Decimal(rng.randrange(150, 3000, 10)),
            date=date,
            installments=rng.choice([1, 1, 2, 3, 4, 6]),
            first_due_date=date,
            user=user,
        )
        for installment in entry.installments.all():
            if installment.due_date <= today and rng.random() < 0.8:
                services.receive(
                    installment,
                    user=user,
                    amount=installment.amount,
                    date=installment.due_date,
                    method=rng.choice(methods),
                    account=rng.choice(accounts),
                )
        created_count += 1
    return created_count, _simulate_expenses(clinic, rng, accounts, user, cost_centers)


# Fake payables: (supplier, description, category, amount, monthly repetitions or None).
SIMULATED_EXPENSES = [
    ("Imobiliária Central", "Aluguel", "Aluguel", 3000, 6),
    ("Companhia de energia", "Água, luz e internet", "Água, luz e internet", 450, 6),
    ("Dental Suprimentos", "Material odontológico", "Material odontológico", 1350, None),
    ("Laboratório Sorriso", "Prótese", "Laboratório de prótese", 980, None),
    ("Contabilidade Ágil", "Honorários contábeis", "Outras despesas", 600, 6),
]


VISIT_EXPENSES = {"Material odontológico", "Laboratório de prótese"}


def _simulate_expenses(clinic, rng, accounts, user, cost_centers):
    """Monthly bills from 2 months ago to 3 months ahead and a few purchases (mostly paid)."""
    from decimal import Decimal

    from apps.finance import payment_methods as payment_methods
    from apps.finance import services
    from apps.finance.models import Category, Entry, Supplier

    # Bills are paid the way the clinic's country pays them (decision 123).
    for_country = payment_methods.for_country(clinic.country).codes
    bill_methods = (
        payment_methods.PIX,
        payment_methods.BOLETO,
        payment_methods.TRANSFER,
        payment_methods.DIRECT_DEBIT,
    )
    methods = [method for method in bill_methods if method in for_country]
    categories = {
        c.name: c for c in Category.objects.filter(clinic=clinic, kind=Category.Kind.EXPENSE)
    }
    today = timezone.localdate()
    start = services.add_months(today.replace(day=10), -2)
    created_recalls = 0
    for supplier, description, category, amount, months in SIMULATED_EXPENSES:
        if category not in categories:
            continue
        installments = months or rng.choice([1, 2, 3])
        amount = Decimal(amount)
        record, _created = Supplier.objects.get_or_create(clinic=clinic, name=supplier)
        entry = services.create_entry(
            clinic=clinic,
            kind=Entry.Kind.PAYABLE,
            supplier=record,
            payer=supplier,
            description=description,
            category=categories[category],
            cost_center=cost_centers[
                "Atendimento" if category in VISIT_EXPENSES else "Administrativo"
            ],
            total_amount=amount * installments if months else amount,
            date=start,
            installments=installments,
            first_due_date=start if months else today - datetime.timedelta(days=20),
            user=user,
        )
        for installment in entry.installments.all():
            if installment.due_date <= today and rng.random() < 0.9:
                services.receive(
                    installment,
                    user=user,
                    amount=installment.amount,
                    date=installment.due_date,
                    method=rng.choice(methods),
                    account=rng.choice(accounts),
                )
        created_recalls += 1
    return created_recalls


# Example price list for a test clinic without one: (name, price).
SAMPLE_PROCEDURES = [
    ("Consulta de avaliação", 150),
    ("Limpeza (profilaxia)", 200),
    ("Restauração em resina", 250),
    ("Extração simples", 300),
    ("Tratamento de canal", 1200),
    ("Clareamento", 900),
    ("Coroa de porcelana", 1800),
    ("Aplicação de flúor", 80),
]


def simulate_estimates(clinic, rng, quantity=20, user=None):
    """Fake estimates of the last 60 days: some approved (they become receivables), some
    refused, the rest open. Creates an example price list if the clinic has none."""
    from decimal import Decimal

    from apps.dentistry.teeth import PERMANENT_TEETH
    from apps.estimates import services
    from apps.estimates.models import (
        Estimate,
        EstimateItem,
        Procedure,
    )
    from apps.finance.models import Category

    treatment = Category.objects.filter(clinic=clinic, name="Tratamento").first()
    if not Procedure.objects.filter(clinic=clinic).exists():
        Procedure.objects.bulk_create(
            Procedure(clinic=clinic, name=name, amount=Decimal(amount), category=treatment)
            for name, amount in SAMPLE_PROCEDURES
        )
    procedures = list(Procedure.objects.filter(clinic=clinic, active=True))
    patients = _patients(clinic)
    practitioners = list(Practitioner.objects.filter(clinic=clinic, active=True))
    category = (
        treatment or Category.objects.filter(clinic=clinic, kind=Category.Kind.INCOME).first()
    )
    if not (procedures and patients and category):
        return 0
    teeth = [d for row in PERMANENT_TEETH for d in row]
    today = timezone.localdate()
    for _ in range(quantity):
        date = today - datetime.timedelta(days=rng.randint(0, 60))
        estimate = Estimate.objects.create(
            clinic=clinic,
            patient=rng.choice(patients),
            practitioner=rng.choice(practitioners) if practitioners else None,
            date=date,
            valid_until=date + datetime.timedelta(days=30),
            created_by=user,
        )
        for procedure in rng.sample(procedures, rng.randint(1, 3)):
            chosen_ones = sorted(rng.sample(teeth, rng.randint(0, 3)))
            EstimateItem.objects.create(
                clinic=clinic,
                estimate=estimate,
                procedure=procedure,
                description=procedure.name,
                teeth=",".join(str(d) for d in chosen_ones),
                quantity=max(len(chosen_ones), 1),
                unit_price=procedure.amount,
            )
        roll = rng.random()
        if roll < 0.4:
            services.approve(
                estimate,
                installments=rng.choice([1, 2, 3, 4]),
                first_due_date=date + datetime.timedelta(days=7),
                category=category,
                user=user,
            )
        elif roll < 0.6:
            services.refuse(estimate, user=user)
    return quantity


def simulate_commissions(clinic, rng, user=None):
    """Give practitioners without one a commission percentage and pay out what each had
    pending up to the end of last month (test clinics only). Returns how many were paid."""
    from decimal import Decimal

    from apps.finance import commissions
    from apps.finance.models import Category

    category = Category.objects.filter(
        clinic=clinic, kind=Category.Kind.EXPENSE, name="Comissões"
    ).first()
    if category is None:
        return 0
    end_of_last_month = timezone.localdate().replace(day=1) - datetime.timedelta(days=1)
    paid_count = 0
    for practitioner in Practitioner.objects.filter(clinic=clinic, active=True):
        if not practitioner.commission_percentage:
            practitioner.commission_percentage = Decimal(rng.choice([30, 35, 40]))
            practitioner.save(update_fields=["commission_percentage"])
        # Runs without isolation (like the command); the practitioner pins the clinic.
        if commissions.pending(practitioner, end_of_last_month)["amount"] > 0:
            commissions.pay(
                practitioner,
                until=end_of_last_month,
                due_date=end_of_last_month + datetime.timedelta(days=5),
                category=category,
                user=user,
            )
            paid_count += 1
    return paid_count
