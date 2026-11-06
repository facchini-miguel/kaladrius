"""Tooth numbering (decision 122): teeth are stored in FDI and shown in the clinic's numbering,
FDI, Universal (United States, the default there) or Palmer."""

import pytest
from django.urls import reverse

from apps.core.forms import NewClinicForm
from apps.core.isolation import use_clinic
from apps.dentistry.teeth import (
    FDI,
    PALMER,
    PERMANENT_TEETH,
    PRIMARY_TEETH,
    UNIVERSAL,
    name,
    sort_teeth,
)
from tests.test_core import clinic_data
from tests.test_estimates import add_item, create_estimate, log_in, scenario  # noqa: F401

pytestmark = pytest.mark.django_db

PERMANENT = [d for row in PERMANENT_TEETH for d in row]
DECIDUOUS = [d for row in PRIMARY_TEETH for d in row]


@pytest.mark.parametrize(
    ("fdi", "universal", "palmer"),
    [
        (18, "1", "UR8"),
        (11, "8", "UR1"),
        (21, "9", "UL1"),
        (28, "16", "UL8"),
        (38, "17", "LL8"),
        (36, "19", "LL6"),
        (31, "24", "LL1"),
        (41, "25", "LR1"),
        (48, "32", "LR8"),
        (55, "A", "URE"),
        (65, "J", "ULE"),
        (75, "K", "LLE"),
        (85, "T", "LRE"),
    ],
)
def test_names_of_each_numbering(fdi, universal, palmer):
    names = (name(fdi, FDI), name(fdi, UNIVERSAL), name(fdi, PALMER))
    assert names == (str(fdi), universal, palmer)


def test_each_tooth_has_one_name():
    for numbering in (FDI, UNIVERSAL, PALMER):
        names = [name(d, numbering) for d in PERMANENT + DECIDUOUS]
        assert len(set(names)) == 52, numbering
    assert sorted(int(name(d, UNIVERSAL)) for d in PERMANENT) == list(range(1, 33))
    assert sorted(name(d, UNIVERSAL) for d in DECIDUOUS) == list("ABCDEFGHIJKLMNOPQRST")


def test_numbering_order():
    assert [name(d, UNIVERSAL) for d in sort_teeth([85, 36, 11, 55, 18], UNIVERSAL)] == [
        "1",
        "8",
        "19",
        "A",
        "T",
    ]
    assert sort_teeth([36, 11], PALMER) == [11, 36]


def test_numbering_follows_the_country(clinic_a, create_user, client_for):
    from apps.core.models import Role

    admin = client_for(create_user("admin_numeracao", clinic_a, Role.ADMIN))
    assert clinic_a.tooth_numbering == FDI
    assert admin.post(reverse("clinic_settings"), clinic_data(country="US")).status_code == 302
    clinic_a.refresh_from_db()
    assert clinic_a.tooth_numbering == UNIVERSAL
    # Chosen on purpose, it stays when the country changes.
    data = clinic_data(country="US", tooth_numbering=PALMER)
    assert admin.post(reverse("clinic_settings"), data).status_code == 302
    data = clinic_data(country="GB", tooth_numbering=PALMER)
    assert admin.post(reverse("clinic_settings"), data).status_code == 302
    clinic_a.refresh_from_db()
    assert clinic_a.tooth_numbering == PALMER


def test_new_clinic_in_united_states_starts_with_universal():
    form = NewClinicForm({"name": "Smile Fictitious", "area": "odontologia", "country": "US"})
    assert form.is_valid(), form.errors
    assert form.instance.tooth_numbering == UNIVERSAL


def test_estimate_shows_the_clinic_numbering(scenario):  # noqa: F811
    clinic = scenario["clinic"]
    clinic.tooth_numbering = UNIVERSAL
    clinic.save()
    user_client = log_in(scenario, "practitioner")
    estimate = create_estimate(scenario, user_client)
    add_item(user_client, estimate, procedure=scenario["restoration"].pk, teeth="36,18")
    with use_clinic(clinic):
        item = estimate.items.get()
        assert item.teeth == "18,36"  # always FDI in the database
        assert item.teeth_display == "1, 19"
    page = user_client.get(reverse("estimates:detail", args=[estimate.pk])).content.decode()
    # The chart posts FDI and shows the Universal number.
    assert 'data-tooth="36"' in page and ">19</button>" in page
    assert "Numeração universal (Estados Unidos)." in page
