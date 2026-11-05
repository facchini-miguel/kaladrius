import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import use_clinic
from apps.core.models import Role
from apps.patients.models import Patient
from apps.recalls.models import Recall

pytestmark = pytest.mark.django_db
DIA = datetime.date(2031, 3, 5)


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    with use_clinic(clinica_a):
        patient = Patient.objects.create(name="João Rechamada")
    return {
        "clinic": clinica_a,
        "patient": patient,
        "cliente": cliente_de(criar_usuario("recepcao", clinica_a, Role.FRONT_DESK)),
    }


def rechamadas(clinic):
    with use_clinic(clinic):
        return list(Recall.objects.order_by("date"))


def criar(clinic, patient, date=DIA, **extra):
    with use_clinic(clinic):
        return Recall.objects.create(patient=patient, date=date, description="Revisão", **extra)


def test_cria_rechamada(cenario):
    response = cenario["cliente"].post(
        reverse("recalls:new"),
        {
            "patient": cenario["patient"].pk,
            "date": DIA.isoformat(),
            "description": "Revisão 6 meses",
        },
    )
    assert response.status_code == 302
    [rechamada] = rechamadas(cenario["clinic"])
    assert rechamada.description == "Revisão 6 meses" and not rechamada.done
    assert rechamada.created_by.username == "recepcao"


def test_paciente_e_obrigatorio(cenario):
    response = cenario["cliente"].post(
        reverse("recalls:new"), {"date": DIA.isoformat(), "description": "x"}
    )
    assert "Escolha o paciente" in response.content.decode()


def test_nova_a_partir_da_ficha_volta_para_a_ficha(cenario):
    ficha = reverse("patients:record", args=[cenario["patient"].pk])
    formulario = cenario["cliente"].get(
        reverse("recalls:new"), {"patient": cenario["patient"].pk, "next": ficha}
    )
    assert "João Rechamada" in formulario.content.decode()
    response = cenario["cliente"].post(
        reverse("recalls:new"),
        {
            "patient": cenario["patient"].pk,
            "date": DIA.isoformat(),
            "description": "x",
            "next": ficha,
        },
    )
    assert response.url == ficha
    assert "Revisão" not in cenario["cliente"].get(ficha).content.decode()  # shows "x"


def test_concluir_e_reabrir(cenario):
    rechamada = criar(cenario["clinic"], cenario["patient"])
    url = reverse("recalls:complete", args=[rechamada.pk])
    assert cenario["cliente"].get(url).status_code == 405
    cenario["cliente"].post(url)
    rechamada.refresh_from_db()
    assert rechamada.done
    cenario["cliente"].post(url)
    rechamada.refresh_from_db()
    assert not rechamada.done


def test_filtros_da_lista(cenario):
    clinic, patient = cenario["clinic"], cenario["patient"]
    criar(clinic, patient, DIA)
    criar(clinic, patient, DIA + datetime.timedelta(days=30), done=True)
    with use_clinic(clinic):
        other = Patient.objects.create(name="Ana Outra")
    criar(clinic, other, DIA + datetime.timedelta(days=60))
    url = reverse("recalls:list")

    def nomes(**params):
        return [r.patient.name for r in cenario["cliente"].get(url, params).context["pagina"]]

    assert nomes() == ["João Rechamada", "Ana Outra"]  # pending, ordered by date
    assert nomes(status="concluidas") == ["João Rechamada"]
    assert nomes(status="todas", q="ana") == ["Ana Outra"]
    assert nomes(status="todas", de="2031-03-06", until="2031-04-30") == ["João Rechamada"]


def test_situacao_atrasada(cenario):
    ontem = timezone.localdate() - datetime.timedelta(days=1)
    criar(cenario["clinic"], cenario["patient"], ontem)
    assert "Atrasada" in cenario["cliente"].get(reverse("recalls:list")).content.decode()


def test_resumo_e_lista_do_dia_para_a_agenda(cenario):
    clinic, patient = cenario["clinic"], cenario["patient"]
    criar(clinic, patient, DIA)
    criar(clinic, patient, DIA)
    criar(clinic, patient, DIA, done=True)
    summary = cenario["cliente"].get(
        reverse("recalls:summary"),
        {"start": "2031-03-03T00:00:00-03:00", "end": "2031-03-10T00:00:00-03:00"},
    )
    assert summary.json() == {"2031-03-05": 2}
    day = cenario["cliente"].get(reverse("recalls:today"), {"date": "2031-03-05"}).content.decode()
    assert day.count("João Rechamada") == 3


def test_agenda_recebe_as_urls_de_rechamadas(cenario, criar_profissional):
    criar_profissional(cenario["clinic"], "Dra. A")
    urls = cenario["cliente"].get(reverse("schedule:calendar")).context["configuracao"]["urls"]
    assert urls["rechamadas"] == reverse("recalls:summary")


def test_isolamento(cenario, clinica_b):
    with use_clinic(clinica_b):
        paciente_b = Patient.objects.create(name="Paciente B")
    de_b = criar(clinica_b, paciente_b)
    cliente = cenario["cliente"]
    assert cliente.get(reverse("recalls:edit", args=[de_b.pk])).status_code == 404
    assert cliente.post(reverse("recalls:complete", args=[de_b.pk])).status_code == 404
    assert len(cliente.get(reverse("recalls:list"), {"status": "todas"}).context["pagina"]) == 0
    response = cliente.post(
        reverse("recalls:new"),
        {"patient": paciente_b.pk, "date": DIA.isoformat(), "description": "x"},
    )
    assert "patient" in response.context["form"].errors


@pytest.mark.parametrize(("role", "exclui"), [(Role.FRONT_DESK, True), (Role.PRACTITIONER, False)])
def test_permissao_de_excluir(role, exclui, cenario, criar_usuario, cliente_de):
    rechamada = criar(cenario["clinic"], cenario["patient"])
    cliente = cliente_de(criar_usuario("usuario", cenario["clinic"], role))
    response = cliente.post(reverse("recalls:delete", args=[rechamada.pk]))
    assert response.status_code == (302 if exclui else 403)


def test_rechamadas_de_paciente_arquivado_saem_das_telas(cenario, criar_usuario, cliente_de):
    rechamada = criar(cenario["clinic"], cenario["patient"])
    admin = cliente_de(criar_usuario("admin", cenario["clinic"], Role.ADMIN))
    admin.post(reverse("patients:archive", args=[cenario["patient"].pk]))
    assert "Maria" not in admin.get(reverse("recalls:list")).content.decode()
    day = admin.get(reverse("recalls:today"), {"date": rechamada.date.isoformat()})
    assert "Maria" not in day.content.decode()

    # Permanent deletion takes the recalls with it.
    admin.post(reverse("patients:delete", args=[cenario["patient"].pk]))
    with use_clinic(cenario["clinic"]):
        assert not Recall.objects.exists()


# --- Birthdays ---------------------------------------------------------------------


def test_aniversariantes_do_mes(cenario):
    clinic = cenario["clinic"]
    with use_clinic(clinic):
        Patient.objects.create(name="Março 20", birth_date=datetime.date(1990, 3, 20))
        Patient.objects.create(name="Março 2", birth_date=datetime.date(2000, 3, 2))
        Patient.objects.create(name="Inativo", birth_date=datetime.date(1990, 3, 1), active=False)
        Patient.objects.create(name="Nascido em abril", birth_date=datetime.date(1990, 4, 1))
    response = cenario["cliente"].get(reverse("patients:birthdays"), {"mes": 3})
    assert [p.name for p, _ in response.context["linhas"]] == ["Março 2", "Março 20"]
    assert "Nascido em abril" not in response.content.decode()
    today = timezone.localdate()
    default = cenario["cliente"].get(reverse("patients:birthdays"))
    assert default.context["mes"] == today.month


def test_aniversariantes_exige_permissao_e_clinica(criar_usuario, cliente_de):
    response = cliente_de(criar_usuario("solto")).get(reverse("patients:birthdays"))
    assert response.status_code == 403


def test_paciente_adulterado_no_formulario_mostra_erro(cenario):
    response = cenario["cliente"].post(
        reverse("recalls:new"), {"patient": "abc", "date": "2031-03-05", "description": "x"}
    )
    assert response.status_code == 200
    assert response.context["form"].errors["patient"]
    assert rechamadas(cenario["clinic"]) == []
