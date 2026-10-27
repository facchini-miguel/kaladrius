import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.isolamento import usar_clinica
from apps.core.models import Papel
from apps.pacientes.models import Paciente
from apps.rechamadas.models import Rechamada

pytestmark = pytest.mark.django_db
DIA = datetime.date(2031, 3, 5)


@pytest.fixture
def cenario(clinica_a, criar_usuario, cliente_de):
    with usar_clinica(clinica_a):
        paciente = Paciente.objects.create(nome="João Rechamada")
    return {
        "clinica": clinica_a,
        "paciente": paciente,
        "cliente": cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO)),
    }


def rechamadas(clinica):
    with usar_clinica(clinica):
        return list(Rechamada.objects.order_by("data"))


def criar(clinica, paciente, data=DIA, **extra):
    with usar_clinica(clinica):
        return Rechamada.objects.create(paciente=paciente, data=data, descricao="Revisão", **extra)


def test_cria_rechamada(cenario):
    resposta = cenario["cliente"].post(
        reverse("rechamadas:novo"),
        {
            "paciente": cenario["paciente"].pk,
            "data": DIA.isoformat(),
            "descricao": "Revisão 6 meses",
        },
    )
    assert resposta.status_code == 302
    [rechamada] = rechamadas(cenario["clinica"])
    assert rechamada.descricao == "Revisão 6 meses" and not rechamada.concluida
    assert rechamada.criado_por.username == "recepcao"


def test_paciente_e_obrigatorio(cenario):
    resposta = cenario["cliente"].post(
        reverse("rechamadas:novo"), {"data": DIA.isoformat(), "descricao": "x"}
    )
    assert "Escolha o paciente" in resposta.content.decode()


def test_nova_a_partir_da_ficha_volta_para_a_ficha(cenario):
    ficha = reverse("pacientes:ficha", args=[cenario["paciente"].pk])
    formulario = cenario["cliente"].get(
        reverse("rechamadas:novo"), {"paciente": cenario["paciente"].pk, "next": ficha}
    )
    assert "João Rechamada" in formulario.content.decode()
    resposta = cenario["cliente"].post(
        reverse("rechamadas:novo"),
        {
            "paciente": cenario["paciente"].pk,
            "data": DIA.isoformat(),
            "descricao": "x",
            "next": ficha,
        },
    )
    assert resposta.url == ficha
    assert "Revisão" not in cenario["cliente"].get(ficha).content.decode()  # shows "x"


def test_concluir_e_reabrir(cenario):
    rechamada = criar(cenario["clinica"], cenario["paciente"])
    url = reverse("rechamadas:concluir", args=[rechamada.pk])
    assert cenario["cliente"].get(url).status_code == 405
    cenario["cliente"].post(url)
    rechamada.refresh_from_db()
    assert rechamada.concluida
    cenario["cliente"].post(url)
    rechamada.refresh_from_db()
    assert not rechamada.concluida


def test_filtros_da_lista(cenario):
    clinica, paciente = cenario["clinica"], cenario["paciente"]
    criar(clinica, paciente, DIA)
    criar(clinica, paciente, DIA + datetime.timedelta(days=30), concluida=True)
    with usar_clinica(clinica):
        outro = Paciente.objects.create(nome="Ana Outra")
    criar(clinica, outro, DIA + datetime.timedelta(days=60))
    url = reverse("rechamadas:lista")

    def nomes(**params):
        return [r.paciente.nome for r in cenario["cliente"].get(url, params).context["pagina"]]

    assert nomes() == ["João Rechamada", "Ana Outra"]  # pending, ordered by date
    assert nomes(situacao="concluidas") == ["João Rechamada"]
    assert nomes(situacao="todas", q="ana") == ["Ana Outra"]
    assert nomes(situacao="todas", de="2031-03-06", ate="2031-04-30") == ["João Rechamada"]


def test_situacao_atrasada(cenario):
    ontem = timezone.localdate() - datetime.timedelta(days=1)
    criar(cenario["clinica"], cenario["paciente"], ontem)
    assert "Atrasada" in cenario["cliente"].get(reverse("rechamadas:lista")).content.decode()


def test_resumo_e_lista_do_dia_para_a_agenda(cenario):
    clinica, paciente = cenario["clinica"], cenario["paciente"]
    criar(clinica, paciente, DIA)
    criar(clinica, paciente, DIA)
    criar(clinica, paciente, DIA, concluida=True)
    resumo = cenario["cliente"].get(
        reverse("rechamadas:resumo"),
        {"start": "2031-03-03T00:00:00-03:00", "end": "2031-03-10T00:00:00-03:00"},
    )
    assert resumo.json() == {"2031-03-05": 2}
    dia = (
        cenario["cliente"]
        .get(reverse("rechamadas:do_dia"), {"data": "2031-03-05"})
        .content.decode()
    )
    assert dia.count("João Rechamada") == 3


def test_agenda_recebe_as_urls_de_rechamadas(cenario, criar_profissional):
    criar_profissional(cenario["clinica"], "Dra. A")
    urls = cenario["cliente"].get(reverse("agenda:calendario")).context["configuracao"]["urls"]
    assert urls["rechamadas"] == reverse("rechamadas:resumo")


def test_isolamento(cenario, clinica_b):
    with usar_clinica(clinica_b):
        paciente_b = Paciente.objects.create(nome="Paciente B")
    de_b = criar(clinica_b, paciente_b)
    cliente = cenario["cliente"]
    assert cliente.get(reverse("rechamadas:editar", args=[de_b.pk])).status_code == 404
    assert cliente.post(reverse("rechamadas:concluir", args=[de_b.pk])).status_code == 404
    assert (
        len(cliente.get(reverse("rechamadas:lista"), {"situacao": "todas"}).context["pagina"]) == 0
    )
    resposta = cliente.post(
        reverse("rechamadas:novo"),
        {"paciente": paciente_b.pk, "data": DIA.isoformat(), "descricao": "x"},
    )
    assert "paciente" in resposta.context["form"].errors


@pytest.mark.parametrize(("papel", "exclui"), [(Papel.RECEPCAO, True), (Papel.PROFISSIONAL, False)])
def test_permissao_de_excluir(papel, exclui, cenario, criar_usuario, cliente_de):
    rechamada = criar(cenario["clinica"], cenario["paciente"])
    cliente = cliente_de(criar_usuario("usuario", cenario["clinica"], papel))
    resposta = cliente.post(reverse("rechamadas:excluir", args=[rechamada.pk]))
    assert resposta.status_code == (302 if exclui else 403)


def test_rechamadas_de_paciente_arquivado_saem_das_telas(cenario, criar_usuario, cliente_de):
    rechamada = criar(cenario["clinica"], cenario["paciente"])
    admin = cliente_de(criar_usuario("admin", cenario["clinica"], Papel.ADMIN))
    admin.post(reverse("pacientes:arquivar", args=[cenario["paciente"].pk]))
    assert "Maria" not in admin.get(reverse("rechamadas:lista")).content.decode()
    dia = admin.get(reverse("rechamadas:do_dia"), {"data": rechamada.data.isoformat()})
    assert "Maria" not in dia.content.decode()

    # Permanent deletion takes the recalls with it.
    admin.post(reverse("pacientes:excluir", args=[cenario["paciente"].pk]))
    with usar_clinica(cenario["clinica"]):
        assert not Rechamada.objects.exists()


# --- Birthdays ---------------------------------------------------------------------


def test_aniversariantes_do_mes(cenario):
    clinica = cenario["clinica"]
    with usar_clinica(clinica):
        Paciente.objects.create(nome="Março 20", data_nascimento=datetime.date(1990, 3, 20))
        Paciente.objects.create(nome="Março 2", data_nascimento=datetime.date(2000, 3, 2))
        Paciente.objects.create(
            nome="Inativo", data_nascimento=datetime.date(1990, 3, 1), ativo=False
        )
        Paciente.objects.create(nome="Nascido em abril", data_nascimento=datetime.date(1990, 4, 1))
    resposta = cenario["cliente"].get(reverse("pacientes:aniversariantes"), {"mes": 3})
    assert [p.nome for p, _ in resposta.context["linhas"]] == ["Março 2", "Março 20"]
    assert "Nascido em abril" not in resposta.content.decode()
    hoje = timezone.localdate()
    padrao = cenario["cliente"].get(reverse("pacientes:aniversariantes"))
    assert padrao.context["mes"] == hoje.month


def test_aniversariantes_exige_permissao_e_clinica(criar_usuario, cliente_de):
    resposta = cliente_de(criar_usuario("solto")).get(reverse("pacientes:aniversariantes"))
    assert resposta.status_code == 403


def test_paciente_adulterado_no_formulario_mostra_erro(cenario):
    resposta = cenario["cliente"].post(
        reverse("rechamadas:novo"), {"paciente": "abc", "data": "2031-03-05", "descricao": "x"}
    )
    assert resposta.status_code == 200
    assert resposta.context["form"].errors["paciente"]
    assert rechamadas(cenario["clinica"]) == []
