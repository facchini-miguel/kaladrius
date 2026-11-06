"""Suppliers (decision 093): register, pick on a payable, history. Fictitious data only."""

import pytest
from django.urls import reverse

from apps.core.isolation import use_clinic
from apps.core.models import GENERAL_MODULES, ModuleCode, Role
from apps.core.modules import configure
from apps.finance.models import Category, Entry, Supplier

pytestmark = pytest.mark.django_db

CNPJ = "11222333000181"


@pytest.fixture
def admin(clinica_a, criar_usuario, cliente_de):
    return cliente_de(criar_usuario("admin_fornecedores", clinica_a, Role.ADMIN))


@pytest.fixture
def supplier(clinica_a):
    with use_clinic(clinica_a):
        return Supplier.objects.create(name="Dental Fictícia", tax_id=CNPJ)


def data(**extra):
    return {"kind": "PJ", "name": "Laboratório Fictício", "active": "on", **extra}


def despesa(clinic, **extra):
    with use_clinic(clinic):
        category = Category.objects.filter(kind=Category.Kind.EXPENSE).first()
    return {
        "supplier": "",
        "payer": "",
        "description": "Material fictício",
        "category": category.pk,
        "amount": "450",
        "mode": "dividir",
        "installments": 3,
        "first_due_date": "2031-01-10",
        "notes": "",
        **extra,
    }


def test_registration_normalizes_document_and_contacts(clinica_a, admin):
    response = admin.post(
        reverse("finance:supplier_new"),
        data(tax_id="11.222.333/0001-81", phone="(48) 3333-4444", whatsapp="48 99999-0000"),
    )
    assert response.status_code == 302
    with use_clinic(clinica_a):
        criado = Supplier.objects.get()
    assert (criado.tax_id, criado.phone, criado.whatsapp) == (
        CNPJ,
        "4833334444",
        "48999990000",
    )
    assert response.url == reverse("finance:supplier", args=[criado.pk])


@pytest.mark.parametrize(
    ("extra", "field"),
    [
        ({"tax_id": "11.222.333/0001-00"}, "tax_id"),
        ({"kind": "PF", "tax_id": "111.111.111-11"}, "tax_id"),
        ({"phone": "1234"}, "phone"),
        ({"name": ""}, "name"),
    ],
)
def test_registration_validations(extra, field, admin):
    response = admin.post(reverse("finance:supplier_new"), data(**extra))
    assert response.status_code == 200
    assert field in response.context["form"].errors


def test_duplicate_document_is_refused(supplier, admin):
    response = admin.post(reverse("finance:supplier_new"), data(tax_id=CNPJ))
    assert "tax_id" in response.context["form"].errors
    editar = admin.post(
        reverse("finance:supplier_edit", args=[supplier.pk]),
        data(name="Dental Fictícia Renomeada", tax_id=CNPJ),
    )
    assert editar.status_code == 302


def test_expense_with_supplier_keeps_name_and_shows_on_record(clinica_a, supplier, admin):
    page = admin.get(reverse("finance:expense_new") + f"?supplier={supplier.pk}")
    assert page.context["form"]["supplier"].value() == str(supplier.pk)
    response = admin.post(reverse("finance:expense_new"), despesa(clinica_a, supplier=supplier.pk))
    assert response.status_code == 302
    with use_clinic(clinica_a):
        entry = Entry.objects.get()
    assert entry.supplier == supplier
    assert entry.payer == "Dental Fictícia"
    patient_record = admin.get(reverse("finance:supplier", args=[supplier.pk]))
    assert len(patient_record.context["parcelas"]) == 3
    assert str(patient_record.context["em_aberto"]) == "450.00"
    results = admin.get(reverse("finance:payables")).content.decode()
    assert reverse("finance:supplier", args=[supplier.pk]) in results
    assert admin.get(reverse("finance:payables") + "?q=Dental").context["pagina"].paginator.count


def test_standalone_expense_without_supplier_still_works(clinica_a, admin):
    response = admin.post(reverse("finance:expense_new"), despesa(clinica_a, payer="Feira"))
    assert response.status_code == 302
    with use_clinic(clinica_a):
        entry = Entry.objects.get()
    assert (entry.supplier, entry.payer) == (None, "Feira")


def test_expense_requires_supplier_or_name(clinica_a, admin):
    response = admin.post(reverse("finance:expense_new"), despesa(clinica_a))
    assert response.status_code == 200
    assert "supplier" in response.context["form"].errors


def test_inactive_supplier_leaves_expense_but_stays_on_list(clinica_a, supplier, admin):
    with use_clinic(clinica_a):
        supplier.active = False
        supplier.save()
    form = admin.get(reverse("finance:expense_new")).context["form"]
    with use_clinic(clinica_a):
        assert supplier not in form.fields["supplier"].queryset
    assert supplier in admin.get(reverse("finance:suppliers")).context["pagina"]


def test_search_by_name_and_document(supplier, admin):
    url = reverse("finance:suppliers")
    assert list(admin.get(url, {"q": "dental ficticia"}).context["pagina"]) == [supplier]
    assert list(admin.get(url, {"q": "11.222.333"}).context["pagina"]) == [supplier]
    assert list(admin.get(url, {"q": "outro"}).context["pagina"]) == []


@pytest.mark.parametrize("role", [Role.FRONT_DESK, Role.PRACTITIONER])
def test_only_finance_people_see_suppliers(role, supplier, clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("sem_financeiro", clinica_a, role))
    for url in (
        reverse("finance:suppliers"),
        reverse("finance:supplier", args=[supplier.pk]),
        reverse("finance:supplier_new"),
    ):
        assert cliente.get(url).status_code == 403, url


def test_finance_role_registers_supplier(clinica_a, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("financeiro_fornecedores", clinica_a, Role.FINANCE))
    assert cliente.post(reverse("finance:supplier_new"), data()).status_code == 302


def test_suppliers_hidden_with_finance_off(clinica_a, supplier, admin):
    assert reverse("finance:suppliers") in admin.get(reverse("home")).content.decode()
    configure(
        clinica_a,
        GENERAL_MODULES - {ModuleCode.FINANCE, ModuleCode.ESTIMATES, ModuleCode.STAFF},
    )
    assert admin.get(reverse("finance:suppliers")).status_code == 403
    assert reverse("finance:suppliers") not in admin.get(reverse("home")).content.decode()


def test_supplier_of_another_clinic_does_not_show(clinica_b, supplier, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("admin_b", clinica_b, Role.ADMIN))
    assert cliente.get(reverse("finance:supplier", args=[supplier.pk])).status_code == 404
