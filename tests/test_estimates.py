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
HOJE = timezone.localdate()


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    with use_clinic(clinica_a):
        patient = Patient.objects.create(name="Joana Sorriso")
        tratamento = Category.objects.get(name="Tratamento")
        canal = Procedure.objects.create(
            name="Tratamento de canal", amount=Decimal("1200"), category=tratamento
        )
        restauracao = Procedure.objects.create(name="Restauração", amount=Decimal("250"))
    return {
        "clinic": clinica_a,
        "patient": patient,
        "canal": canal,
        "restauracao": restauracao,
        "admin": criar_usuario("admin", clinica_a, Role.ADMIN),
        "recepcao": criar_usuario("recepcao", clinica_a, Role.FRONT_DESK),
        "practitioner": criar_usuario("dra", clinica_a, Role.PRACTITIONER),
        "cliente_de": cliente_de,
    }


def entrar(cenario, quem):
    return cenario["cliente_de"](cenario[quem])


def criar_orcamento(cenario, cliente):
    response = cliente.post(
        reverse("estimates:new"),
        {
            "patient": cenario["patient"].pk,
            "practitioner": "",
            "date": HOJE.isoformat(),
            "valid_until": HOJE.isoformat(),
            "notes": "",
        },
    )
    with use_clinic(cenario["clinic"]):
        estimate = Estimate.objects.latest("pk")
    assert response.url == reverse("estimates:detail", args=[estimate.pk])
    return estimate


def incluir(cliente, estimate, **data):
    return cliente.post(
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


def test_practitioner_builds_estimate_with_teeth(cenario):
    cliente = entrar(cenario, "practitioner")
    estimate = criar_orcamento(cenario, cliente)
    # Description and price come from the price list; teeth are normalized.
    incluir(cliente, estimate, procedure=cenario["restauracao"].pk, teeth="36, 11,11", quantity=2)
    incluir(cliente, estimate, description="Moldagem", unit_price="80,00")
    with use_clinic(cenario["clinic"]):
        itens = list(estimate.itens.order_by("pk"))
        estimate.refresh_from_db()
        assert estimate.total == Decimal("580.00")
        assert estimate.teeth == [11, 36]
    assert (itens[0].description, itens[0].teeth, itens[0].unit_price) == (
        "Restauração",
        "11,36",
        Decimal("250.00"),
    )
    assert itens[0].teeth_display == "11, 36"
    page = cliente.get(reverse("estimates:detail", args=[estimate.pk])).content.decode()
    assert 'data-tooth="36"' in page and "R$ 580,00" in page


@pytest.mark.parametrize(
    "data",
    [
        {"teeth": "19"},  # no such tooth
        {"procedure": ""},  # neither procedure nor description
    ],
)
def test_invalid_items(cenario, data):
    cliente = entrar(cenario, "recepcao")
    estimate = criar_orcamento(cenario, cliente)
    incluir(cliente, estimate, **{"procedure": cenario["canal"].pk, **data})
    with use_clinic(cenario["clinic"]):
        assert not estimate.itens.exists()


def test_estimate_author_gives_discount(cenario):
    # Front desk, practitioner and administrator (0.27.1, decision 074).
    reception = entrar(cenario, "recepcao")
    estimate = criar_orcamento(cenario, reception)
    incluir(reception, estimate, procedure=cenario["canal"].pk)
    url = reverse("estimates:discount", args=[estimate.pk])
    assert reception.get(reverse("estimates:detail", args=[estimate.pk])).context["discount_form"]
    reception.post(url, {"discount": "5000"})  # more than the total: refused
    estimate.refresh_from_db()
    assert estimate.discount == 0
    reception.post(url, {"discount": "200"})
    estimate.refresh_from_db()
    assert estimate.discount == Decimal("200.00")
    for quem, amount in [("practitioner", "150"), ("admin", "100")]:
        entrar(cenario, quem).post(url, {"discount": amount})
        estimate.refresh_from_db()
        assert estimate.discount == Decimal(amount)


def test_approving_becomes_a_receivable(cenario):
    reception = entrar(cenario, "recepcao")
    estimate = criar_orcamento(cenario, reception)
    incluir(reception, estimate, procedure=cenario["canal"].pk)
    with use_clinic(cenario["clinic"]):
        Estimate.objects.filter(pk=estimate.pk).update(discount=Decimal("200"))
        cash_register = FinancialAccount.objects.get(name="Caixa")
    url = reverse("estimates:approve", args=[estimate.pk])
    # The category comes from the first procedure.
    assert reception.get(url).context["form"].initial["category"] == cenario["canal"].category
    response = reception.post(
        url,
        {
            "installments": 4,
            "first_due_date": HOJE.isoformat(),
            "category": cenario["canal"].category.pk,
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
    with use_clinic(cenario["clinic"]):
        assert entry.parcelas.count() == 4
        assert entry.patient == cenario["patient"]
    # Once approved, nothing changes any more.
    incluir(reception, estimate, procedure=cenario["restauracao"].pk)
    with use_clinic(cenario["clinic"]):
        assert estimate.itens.count() == 1
    assert reception.post(reverse("estimates:decline", args=[estimate.pk])).status_code == 302
    estimate.refresh_from_db()
    assert estimate.status == Estimate.Status.APPROVED


def test_practitioner_does_not_approve(cenario):
    cliente = entrar(cenario, "practitioner")
    estimate = criar_orcamento(cenario, cliente)
    assert cliente.get(reverse("estimates:approve", args=[estimate.pk])).status_code == 403
    assert not cliente.get(reverse("estimates:detail", args=[estimate.pk])).context["can_approve"]


def test_refuse_and_print(cenario):
    cliente = entrar(cenario, "recepcao")
    estimate = criar_orcamento(cenario, cliente)
    incluir(cliente, estimate, procedure=cenario["canal"].pk, teeth="46")
    page = cliente.get(reverse("estimates:print", args=[estimate.pk])).content.decode()
    assert "ORÇAMENTO" in page and "Joana Sorriso" in page and 'class="tooth selected' in page
    cliente.post(reverse("estimates:decline", args=[estimate.pk]))
    estimate.refresh_from_db()
    assert estimate.status == Estimate.Status.REFUSED
    # Deciding again (e.g. a stale page approving it meanwhile) is refused.
    with use_clinic(cenario["clinic"]), pytest.raises(ValidationError):
        services.refuse(estimate, user=None)
    estimate_list = cliente.get(reverse("estimates:list"), {"status": "recusado"})
    assert list(estimate_list.context["page"]) == [estimate]


def test_record_shows_estimates_and_archived_hides(cenario):
    cliente = entrar(cenario, "recepcao")
    estimate = criar_orcamento(cenario, cliente)
    patient_record = cliente.get(reverse("patients:record", args=[cenario["patient"].pk]))
    assert patient_record.context["estimates"] == [estimate]
    with use_clinic(cenario["clinic"]):
        Patient.objects.filter(pk=cenario["patient"].pk).update(archived=True)
    assert cliente.get(reverse("estimates:detail", args=[estimate.pk])).status_code == 404


def test_only_admin_changes_procedure_table(cenario):
    reception = entrar(cenario, "recepcao")
    assert reception.get(reverse("estimates:procedures")).status_code == 200
    assert reception.get(reverse("estimates:procedure_new")).status_code == 403
    admin = entrar(cenario, "admin")
    url = reverse("estimates:procedure_new")
    assert (
        admin.post(url, {"name": "Clareamento", "amount": "900", "active": "on"}).status_code == 302
    )
    assert "Já existe" in admin.post(url, {"name": "Clareamento", "amount": "1"}).content.decode()


def test_permanent_deletion_deletes_the_estimates(cenario):
    admin = entrar(cenario, "admin")
    estimate = criar_orcamento(cenario, admin)
    incluir(admin, estimate, procedure=cenario["canal"].pk, teeth="11")
    with use_clinic(cenario["clinic"]):
        Patient.objects.filter(pk=cenario["patient"].pk).update(archived=True)
    admin.post(reverse("patients:delete", args=[cenario["patient"].pk]))
    with use_clinic(cenario["clinic"]):
        assert not Estimate.objects.exists() and not EstimateItem.objects.exists()


def test_estimate_of_another_clinic_gives_404(cenario, clinica_b, criar_usuario, cliente_de):
    estimate = criar_orcamento(cenario, entrar(cenario, "recepcao"))
    other = cliente_de(criar_usuario("admin_b", clinica_b, Role.ADMIN))
    assert other.get(reverse("estimates:detail", args=[estimate.pk])).status_code == 404


def test_odontogram_only_in_dentistry(cenario):
    # Decision 080: teeth and faces belong to the dental module.
    from apps.core.models import Clinic

    reception = entrar(cenario, "recepcao")
    estimate = criar_orcamento(cenario, reception)
    estimate_detail = reverse("estimates:detail", args=[estimate.pk])
    page = reception.get(estimate_detail)
    assert page.context["show_teeth"] and 'class="odontogram-scroll"' in page.content.decode()
    assert "teeth" in page.context["item_form"].fields

    from apps.core.models import GENERAL_MODULES
    from apps.core.modules import configure

    configure(cenario["clinic"], {*GENERAL_MODULES, Clinic.Area.MEDICINE})
    page = reception.get(estimate_detail)
    assert not page.context["show_teeth"]
    assert 'class="odontogram-scroll"' not in page.content.decode()
    assert "teeth" not in page.context["item_form"].fields
    incluir(reception, estimate, procedure=cenario["canal"].pk, teeth="11", faces="V")
    with use_clinic(cenario["clinic"]):
        assert not estimate.itens.exists()  # forged fields are rejected, not discarded
    configure(cenario["clinic"], {*GENERAL_MODULES, Clinic.Area.DENTISTRY})
    incluir(reception, estimate, procedure=cenario["canal"].pk, teeth="11", faces="V")
    configure(cenario["clinic"], {*GENERAL_MODULES, Clinic.Area.MEDICINE})
    page = reception.get(estimate_detail)
    assert page.context["show_teeth"] and "11" in page.content.decode()
    impressao = reception.get(reverse("estimates:print", args=[estimate.pk]))
    assert impressao.context["show_teeth"]
