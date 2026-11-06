"""Procedure price list and treatment estimates (0.18.0)."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.estimates import services
from apps.estimates.models import Estimate, EstimateItem, Procedure
from apps.finance.models import Category, Entry, FinancialAccount
from apps.patients.models import Patient

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()


@pytest.fixture
def scenario(clinic_a, create_user, client_for):
    with use_clinic(clinic_a):
        patient = Patient.objects.create(name="Joana Sorriso")
        treatment = Category.objects.get(name="Tratamento")
        channel = Procedure.objects.create(
            name="Tratamento de canal", amount=Decimal("1200"), category=treatment
        )
        restoration = Procedure.objects.create(name="Restauração", amount=Decimal("250"))
    return {
        "clinic": clinic_a,
        "patient": patient,
        "channel": channel,
        "restoration": restoration,
        "admin": create_user("admin", clinic_a, Role.ADMIN),
        "reception": create_user("recepcao", clinic_a, Role.FRONT_DESK),
        "practitioner": create_user("dra", clinic_a, Role.PRACTITIONER),
        "client_for": client_for,
    }


def log_in(scenario, who):
    return scenario["client_for"](scenario[who])


def create_estimate(scenario, user_client):
    response = user_client.post(
        reverse("estimates:new"),
        {
            "patient": scenario["patient"].pk,
            "practitioner": "",
            "date": TODAY.isoformat(),
            "valid_until": TODAY.isoformat(),
            "notes": "",
        },
    )
    with use_clinic(scenario["clinic"]):
        estimate = Estimate.objects.latest("pk")
    assert response.url == reverse("estimates:detail", args=[estimate.pk])
    return estimate


def add_item(user_client, estimate, **data):
    return user_client.post(
        reverse("estimates:item_add", args=[estimate.pk]),
        {
            "description": "",
            "teeth": "",
            "faces": "",
            "quantity": 1,
            "unit_price": "",
            **data,
        },
    )


def test_practitioner_builds_estimate_with_teeth(scenario):
    user_client = log_in(scenario, "practitioner")
    estimate = create_estimate(scenario, user_client)
    # Description and price come from the price list; teeth are normalized.
    add_item(
        user_client, estimate, procedure=scenario["restoration"].pk, teeth="36, 11,11", quantity=2
    )
    add_item(user_client, estimate, description="Moldagem", unit_price="80,00")
    with use_clinic(scenario["clinic"]):
        items = list(estimate.items.order_by("pk"))
        estimate.refresh_from_db()
        assert estimate.total == Decimal("580.00")
        assert estimate.teeth == [11, 36]
    assert (items[0].description, items[0].teeth, items[0].unit_price) == (
        "Restauração",
        "11,36",
        Decimal("250.00"),
    )
    assert items[0].teeth_display == "11, 36"
    page = user_client.get(reverse("estimates:detail", args=[estimate.pk])).content.decode()
    assert 'data-tooth="36"' in page and "R$ 580,00" in page


@pytest.mark.parametrize(
    "data",
    [
        {"teeth": "19"},  # no such tooth
        {"procedure": ""},  # neither procedure nor description
    ],
)
def test_invalid_items(scenario, data):
    user_client = log_in(scenario, "reception")
    estimate = create_estimate(scenario, user_client)
    add_item(user_client, estimate, **{"procedure": scenario["channel"].pk, **data})
    with use_clinic(scenario["clinic"]):
        assert not estimate.items.exists()


def test_estimate_author_gives_discount(scenario):
    # Front desk, practitioner and administrator (0.27.1, decision 074).
    reception = log_in(scenario, "reception")
    estimate = create_estimate(scenario, reception)
    add_item(reception, estimate, procedure=scenario["channel"].pk)
    url = reverse("estimates:discount", args=[estimate.pk])
    assert reception.get(reverse("estimates:detail", args=[estimate.pk])).context["discount_form"]
    reception.post(url, {"discount": "5000"})  # more than the total: refused
    estimate.refresh_from_db()
    assert estimate.discount == 0
    reception.post(url, {"discount": "200"})
    estimate.refresh_from_db()
    assert estimate.discount == Decimal("200.00")
    for who, amount in [("practitioner", "150"), ("admin", "100")]:
        log_in(scenario, who).post(url, {"discount": amount})
        estimate.refresh_from_db()
        assert estimate.discount == Decimal(amount)


def test_approving_becomes_a_receivable(scenario):
    reception = log_in(scenario, "reception")
    estimate = create_estimate(scenario, reception)
    add_item(reception, estimate, procedure=scenario["channel"].pk)
    with use_clinic(scenario["clinic"]):
        Estimate.objects.filter(pk=estimate.pk).update(discount=Decimal("200"))
        cash_register = FinancialAccount.objects.get(name="Caixa")
    url = reverse("estimates:approve", args=[estimate.pk])
    # The category comes from the first procedure.
    assert reception.get(url).context["form"].initial["category"] == scenario["channel"].category
    response = reception.post(
        url,
        {
            "installments": 4,
            "first_due_date": TODAY.isoformat(),
            "category": scenario["channel"].category.pk,
            "received_now": "on",
            "method": "pix",
            "account": cash_register.pk,
        },
    )
    estimate.refresh_from_db()
    entry = estimate.entry
    assert response.url == reverse("finance:entry", args=[entry.pk])
    assert estimate.status == Estimate.Status.APPROVED
    assert (entry.kind, entry.total_amount) == (
        Entry.Kind.RECEIVABLE,
        Decimal("1000.00"),
    )
    with use_clinic(scenario["clinic"]):
        assert entry.installments.count() == 4
        assert entry.patient == scenario["patient"]
    # Once approved, nothing changes any more.
    add_item(reception, estimate, procedure=scenario["restoration"].pk)
    with use_clinic(scenario["clinic"]):
        assert estimate.items.count() == 1
    assert reception.post(reverse("estimates:decline", args=[estimate.pk])).status_code == 302
    estimate.refresh_from_db()
    assert estimate.status == Estimate.Status.APPROVED


def test_practitioner_does_not_approve(scenario):
    user_client = log_in(scenario, "practitioner")
    estimate = create_estimate(scenario, user_client)
    assert user_client.get(reverse("estimates:approve", args=[estimate.pk])).status_code == 403
    assert not user_client.get(reverse("estimates:detail", args=[estimate.pk])).context[
        "can_approve"
    ]


def test_refuse_and_print(scenario):
    user_client = log_in(scenario, "reception")
    estimate = create_estimate(scenario, user_client)
    add_item(user_client, estimate, procedure=scenario["channel"].pk, teeth="46")
    page = user_client.get(reverse("estimates:print", args=[estimate.pk])).content.decode()
    assert "ORÇAMENTO" in page and "Joana Sorriso" in page and 'class="tooth selected' in page
    user_client.post(reverse("estimates:decline", args=[estimate.pk]))
    estimate.refresh_from_db()
    assert estimate.status == Estimate.Status.REFUSED
    # Deciding again (e.g. a stale page approving it meanwhile) is refused.
    with use_clinic(scenario["clinic"]), pytest.raises(ValidationError):
        services.refuse(estimate, user=None)
    estimate_list = user_client.get(reverse("estimates:list"), {"status": "recusado"})
    assert list(estimate_list.context["page"]) == [estimate]


def test_record_shows_estimates_and_archived_hides(scenario):
    user_client = log_in(scenario, "reception")
    estimate = create_estimate(scenario, user_client)
    patient_record = user_client.get(reverse("patients:record", args=[scenario["patient"].pk]))
    assert patient_record.context["estimates"] == [estimate]
    with use_clinic(scenario["clinic"]):
        Patient.objects.filter(pk=scenario["patient"].pk).update(archived=True)
    assert user_client.get(reverse("estimates:detail", args=[estimate.pk])).status_code == 404


def test_only_admin_changes_procedure_table(scenario):
    reception = log_in(scenario, "reception")
    assert reception.get(reverse("estimates:procedures")).status_code == 200
    assert reception.get(reverse("estimates:procedure_new")).status_code == 403
    admin = log_in(scenario, "admin")
    url = reverse("estimates:procedure_new")
    assert (
        admin.post(url, {"name": "Clareamento", "amount": "900", "active": "on"}).status_code == 302
    )
    assert "Já existe" in admin.post(url, {"name": "Clareamento", "amount": "1"}).content.decode()


def test_permanent_deletion_deletes_the_estimates(scenario):
    admin = log_in(scenario, "admin")
    estimate = create_estimate(scenario, admin)
    add_item(admin, estimate, procedure=scenario["channel"].pk, teeth="11")
    with use_clinic(scenario["clinic"]):
        Patient.objects.filter(pk=scenario["patient"].pk).update(archived=True)
    admin.post(reverse("patients:delete", args=[scenario["patient"].pk]))
    with use_clinic(scenario["clinic"]):
        assert not Estimate.objects.exists() and not EstimateItem.objects.exists()


def test_estimate_of_another_clinic_gives_404(scenario, clinic_b, create_user, client_for):
    estimate = create_estimate(scenario, log_in(scenario, "reception"))
    other = client_for(create_user("admin_b", clinic_b, Role.ADMIN))
    assert other.get(reverse("estimates:detail", args=[estimate.pk])).status_code == 404


def test_odontogram_only_in_dentistry(scenario):
    # Decision 080: teeth and faces belong to the dental module.
    from apps.core.models import Clinic

    reception = log_in(scenario, "reception")
    estimate = create_estimate(scenario, reception)
    estimate_detail = reverse("estimates:detail", args=[estimate.pk])
    page = reception.get(estimate_detail)
    assert page.context["show_teeth"] and 'class="odontogram-scroll"' in page.content.decode()
    assert "teeth" in page.context["item_form"].fields

    from apps.core.models import GENERAL_MODULES
    from apps.core.modules import configure

    configure(scenario["clinic"], {*GENERAL_MODULES, Clinic.Area.MEDICINE})
    page = reception.get(estimate_detail)
    assert not page.context["show_teeth"]
    assert 'class="odontogram-scroll"' not in page.content.decode()
    assert "teeth" not in page.context["item_form"].fields
    add_item(reception, estimate, procedure=scenario["channel"].pk, teeth="11", faces="V")
    with use_clinic(scenario["clinic"]):
        assert not estimate.items.exists()  # forged fields are rejected, not discarded
    configure(scenario["clinic"], {*GENERAL_MODULES, Clinic.Area.DENTISTRY})
    add_item(reception, estimate, procedure=scenario["channel"].pk, teeth="11", faces="V")
    configure(scenario["clinic"], {*GENERAL_MODULES, Clinic.Area.MEDICINE})
    page = reception.get(estimate_detail)
    assert page.context["show_teeth"] and "11" in page.content.decode()
    printout = reception.get(reverse("estimates:print", args=[estimate.pk]))
    assert printout.context["show_teeth"]
