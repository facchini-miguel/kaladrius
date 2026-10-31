import datetime
import json

import pytest
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.agenda import servicos
from apps.agenda.forms import AgendamentoForm
from apps.agenda.models import Agendamento, TipoAtendimento
from apps.core.isolamento import SemClinicaAtual, usar_clinica
from apps.core.models import Papel
from apps.financeiro.models import Pagamento
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional
from apps.rechamadas.models import Rechamada

pytestmark = pytest.mark.django_db

# A Monday well in the future, so tests never depend on today's date.
SEGUNDA = datetime.date(2031, 3, 3)


@pytest.fixture
def cenario(clinica_a, criar_profissional, criar_usuario, cliente_de):
    """Clinic A with two practitioners, a type, a patient and a front desk user."""
    with usar_clinica(clinica_a):
        tipo = TipoAtendimento.objects.get(nome="Cirurgia")
        paciente = Paciente.objects.create(nome="Maria Paciente")
    return {
        "clinica": clinica_a,
        "ana": criar_profissional(clinica_a, "Dra. Ana"),
        "bruno": criar_profissional(clinica_a, "Dr. Bruno"),
        "tipo": tipo,
        "paciente": paciente,
        "cliente": cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO)),
    }


def dados(cenario, **extra):
    return {
        "profissional": cenario["ana"].pk,
        "tipo": cenario["tipo"].pk,
        "paciente": cenario["paciente"].pk,
        "descricao": "",
        "data": SEGUNDA.isoformat(),
        "hora_inicio": "09:00",
        "hora_fim": "10:00",
        "repeticoes": 1,
        **extra,
    }


def agendar(cenario, **extra):
    return cenario["cliente"].post(reverse("agenda:novo"), dados(cenario, **extra))


def agendamentos(cenario):
    with usar_clinica(cenario["clinica"]):
        return list(Agendamento.objects.order_by("inicio"))


def erros(resposta):
    form = resposta.context["form"]
    return " ".join(str(e) for lista in form.errors.values() for e in lista)


# --- Creating ----------------------------------------------------------------------


def test_cria_agendamento_e_avisa_a_tela(cenario):
    resposta = agendar(cenario)
    assert resposta.status_code == 204
    assert json.loads(resposta["HX-Trigger"]) == {
        "agendaAtualizada": {"mensagem": "Agendamento criado."}
    }
    [agendamento] = agendamentos(cenario)
    assert agendamento.paciente == cenario["paciente"]
    assert agendamento.criado_por.username == "recepcao"
    assert agendamento.serie is None


def test_repeticao_semanal_cria_a_serie(cenario):
    assert agendar(cenario, repeticoes=4).status_code == 204
    criados = agendamentos(cenario)
    assert len(criados) == 4
    assert len({a.serie for a in criados}) == 1 and criados[0].serie is not None
    datas = [a.inicio.date() for a in criados]
    assert datas == [SEGUNDA + datetime.timedelta(weeks=n) for n in range(4)]


def test_sem_paciente_exige_descricao(cenario):
    resposta = agendar(cenario, paciente="", descricao="")
    assert "Informe o paciente ou uma descrição" in erros(resposta)
    assert agendar(cenario, paciente="", descricao="Reunião de equipe").status_code == 204
    assert agendamentos(cenario)[0].titulo == "Reunião de equipe"


# --- Time rules --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("inicio", "fim", "mensagem"),
    [
        ("09:15", "10:00", "de 30 em 30 minutos"),
        ("09:00", "09:00", "O fim deve ser depois do início"),
        ("10:00", "09:00", "O fim deve ser depois do início"),
        ("06:00", "07:00", "Fora do horário de atendimento"),
        ("19:30", "20:30", "Fora do horário de atendimento"),
    ],
)
def test_regras_de_horario(cenario, inicio, fim, mensagem):
    resposta = agendar(cenario, hora_inicio=inicio, hora_fim=fim)
    assert resposta.status_code == 200
    assert mensagem in erros(resposta)
    assert agendamentos(cenario) == []


def test_intervalo_configurado_pela_clinica(cenario):
    clinica = cenario["clinica"]
    clinica.agenda_intervalo = 15
    clinica.save()
    assert agendar(cenario, hora_inicio="09:15", hora_fim="09:45").status_code == 204


# --- Conflicts ---------------------------------------------------------------------


def test_conflito_com_o_mesmo_profissional(cenario):
    agendar(cenario)
    resposta = agendar(cenario, hora_inicio="09:30", hora_fim="10:30")
    assert resposta.status_code == 200
    assert "Conflito de horário" in erros(resposta)
    assert "Maria Paciente" in erros(resposta)
    assert len(agendamentos(cenario)) == 1


def test_horarios_encostados_e_outro_profissional_nao_conflitam(cenario):
    agendar(cenario)
    assert agendar(cenario, hora_inicio="10:00", hora_fim="10:30").status_code == 204
    assert agendar(cenario, hora_inicio="08:30", hora_fim="09:00").status_code == 204
    assert agendar(cenario, profissional=cenario["bruno"].pk).status_code == 204
    assert len(agendamentos(cenario)) == 4


def test_repeticao_com_conflito_nao_grava_nenhuma(cenario):
    terceira_semana = SEGUNDA + datetime.timedelta(weeks=2)
    agendar(cenario, data=terceira_semana.isoformat())
    resposta = agendar(cenario, repeticoes=4)
    assert resposta.status_code == 200
    assert terceira_semana.strftime("%d/%m") in erros(resposta)
    assert "Nada foi gravado" in erros(resposta)
    assert len(agendamentos(cenario)) == 1


def test_banco_de_dados_impede_sobreposicao(cenario):
    """Even bypassing the form (e.g. two simultaneous requests), the database refuses."""
    with usar_clinica(cenario["clinica"]):
        intervalos = servicos.ocorrencias(SEGUNDA, datetime.time(9), datetime.time(10))
        modelo = Agendamento(
            profissional=cenario["ana"], tipo=cenario["tipo"], descricao="Primeiro"
        )
        servicos.criar(modelo, intervalos, None)
        sobreposto = servicos.ocorrencias(SEGUNDA, datetime.time(9, 30), datetime.time(10, 30))
        with pytest.raises(IntegrityError), transaction.atomic():
            servicos.criar(modelo, sobreposto, None)


# --- Editing and deleting ----------------------------------------------------------


def test_editar_muda_o_horario_sem_conflitar_consigo_mesmo(cenario):
    agendar(cenario)
    [agendamento] = agendamentos(cenario)
    url = reverse("agenda:editar", args=[agendamento.pk])
    formulario = cenario["cliente"].get(url)
    assert formulario.context["form"].initial["hora_inicio"] == datetime.time(9)
    assert "repeticoes" not in formulario.context["form"].fields
    resposta = cenario["cliente"].post(url, dados(cenario, hora_inicio="09:30", hora_fim="10:30"))
    assert resposta.status_code == 204
    agendamento.refresh_from_db()
    assert agendamento.inicio.astimezone().time() == datetime.time(9, 30)


def test_horario_desmarcado_recebe_outro_paciente_sem_apagar_quem_desmarcou(cenario):
    """Round 2: the cancelled appointment covers the freed slot on the calendar, and changing
    its patient overwrote the record of who cancelled."""
    agendar(cenario)
    [agendamento] = agendamentos(cenario)
    cliente = cenario["cliente"]
    cliente.post(reverse("agenda:situacao", args=[agendamento.pk]), {"situacao": "desmarcou"})
    janela = cliente.get(reverse("agenda:editar", args=[agendamento.pk])).content.decode()
    assert "Agendar outro paciente neste horário" in janela
    assert f"{reverse('agenda:novo')}?profissional={cenario['ana'].pk}&amp;data={SEGUNDA}" in janela
    with usar_clinica(cenario["clinica"]):
        outro = Paciente.objects.create(nome="Outro Paciente")
    troca = cliente.post(
        reverse("agenda:editar", args=[agendamento.pk]), dados(cenario, paciente=outro.pk)
    )
    assert "paciente" in troca.context["form"].errors
    novo = cliente.post(reverse("agenda:novo"), dados(cenario, paciente=outro.pk))
    assert novo.status_code == 204
    with usar_clinica(cenario["clinica"]):
        nomes = sorted((a.paciente.nome, a.situacao) for a in Agendamento.objects.all())
    assert nomes == [("Maria Paciente", "desmarcou"), ("Outro Paciente", "agendado")]


def test_excluir_um_ou_a_serie_dali_em_diante(cenario, criar_usuario, cliente_de):
    agendar(cenario, repeticoes=4)
    criados = agendamentos(cenario)
    admin = cliente_de(criar_usuario("admin", cenario["clinica"], Papel.ADMIN))

    admin.post(reverse("agenda:excluir", args=[criados[0].pk]), {"escopo": "este"})
    assert len(agendamentos(cenario)) == 3

    pagina = admin.get(reverse("agenda:excluir", args=[criados[1].pk])).content.decode()
    assert "os próximos 2" in pagina
    resposta = admin.post(reverse("agenda:excluir", args=[criados[1].pk]), {"escopo": "serie"})
    assert json.loads(resposta["HX-Trigger"])["agendaAtualizada"]["mensagem"] == (
        "3 agendamentos excluídos."
    )
    assert agendamentos(cenario) == []


def test_paciente_arquivado_some_das_sugestoes_mas_fica_na_agenda(
    cenario, criar_usuario, cliente_de
):
    agendar(cenario)
    with usar_clinica(cenario["clinica"]):
        Paciente.objects.filter(pk=cenario["paciente"].pk).update(arquivado=True)
    sugestoes = cenario["cliente"].get(reverse("pacientes:sugestoes"), {"q": "maria"})
    assert "Maria Paciente" not in sugestoes.content.decode()
    periodo = {"start": "2031-03-03T00:00:00", "end": "2031-03-10T00:00:00"}
    eventos = cenario["cliente"].get(
        reverse("agenda:eventos"), {**periodo, "profissional": cenario["ana"].pk}
    )
    assert [e["title"] for e in eventos.json()] == ["Maria Paciente"]  # history kept


def test_exclusao_definitiva_tira_o_paciente_dos_agendamentos(cenario, criar_usuario, cliente_de):
    agendar(cenario)
    admin = cliente_de(criar_usuario("admin", cenario["clinica"], Papel.ADMIN))
    paciente = cenario["paciente"]
    admin.post(reverse("pacientes:arquivar", args=[paciente.pk]))
    assert admin.post(reverse("pacientes:excluir", args=[paciente.pk])).status_code == 302
    [agendamento] = agendamentos(cenario)
    assert agendamento.paciente is None
    # The slot stays taken, without the notes (they may hold personal data).
    assert agendamento.descricao == f"Paciente excluído (código {paciente.pk})"
    with usar_clinica(cenario["clinica"]):
        assert not Paciente.objects.filter(pk=paciente.pk).exists()


# --- Calendar feeds ----------------------------------------------------------------


def test_eventos_do_periodo_em_json(cenario):
    agendar(cenario)
    agendar(cenario, data=(SEGUNDA + datetime.timedelta(weeks=1)).isoformat())
    resposta = cenario["cliente"].get(
        reverse("agenda:eventos"),
        {
            "profissional": cenario["ana"].pk,
            "start": f"{SEGUNDA}T00:00:00-03:00",
            "end": f"{SEGUNDA + datetime.timedelta(days=7)}T00:00:00-03:00",
        },
    )
    [evento] = resposta.json()
    assert evento["title"] == "Maria Paciente"
    assert evento["start"].startswith(f"{SEGUNDA}T09:00:00")
    assert evento["backgroundColor"] == "#f7a5a5"
    assert evento["extendedProps"]["tipo"] == "Cirurgia"


def test_eventos_com_parametros_invalidos(cenario):
    url = reverse("agenda:eventos")
    assert cenario["cliente"].get(url, {"profissional": "x"}).status_code == 400
    longo = {"profissional": 1, "start": "2031-01-01", "end": "2031-12-31"}
    assert cenario["cliente"].get(url, longo).status_code == 400


def test_aniversariantes_no_periodo(cenario):
    with usar_clinica(cenario["clinica"]):
        Paciente.objects.create(nome="Aniversariante", data_nascimento=datetime.date(1990, 3, 5))
        Paciente.objects.create(
            nome="Inativo", data_nascimento=datetime.date(1990, 3, 5), ativo=False
        )
    resposta = cenario["cliente"].get(
        reverse("agenda:aniversariantes"),
        {"start": f"{SEGUNDA}T00:00:00", "end": f"{SEGUNDA + datetime.timedelta(days=7)}T00:00:00"},
    )
    assert resposta.json() == {"2031-03-05": 1}
    lista = cenario["cliente"].get(reverse("agenda:aniversariantes_dia"), {"data": "2031-03-05"})
    assert "Aniversariante" in lista.content.decode()
    assert "completa 41 anos" in lista.content.decode()


def test_calendario_abre_no_profissional_escolhido(cenario):
    pagina = cenario["cliente"].get(
        reverse("agenda:calendario"), {"profissional": cenario["bruno"].pk}
    )
    assert pagina.context["profissional"] == cenario["bruno"]
    config = pagina.context["configuracao"]
    assert config["intervalo"] == 30 and config["inicio"] == "07:30:00"
    assert config["pode"] == {"criar": True, "alterar": True}
    # The choice is remembered for the next visit.
    assert (
        cenario["cliente"].get(reverse("agenda:calendario")).context["profissional"]
        == cenario["bruno"]
    )


# --- Isolation and permissions -----------------------------------------------------


def test_agenda_de_outra_clinica_e_invisivel(cenario, clinica_b, criar_profissional):
    de_b = criar_profissional(clinica_b, "Dr. B")
    with usar_clinica(clinica_b):
        tipo_b = TipoAtendimento.objects.get(nome="Cirurgia")
        paciente_b = Paciente.objects.create(nome="Paciente B")
        [agendamento_b] = servicos.criar(
            Agendamento(profissional=de_b, tipo=tipo_b, paciente=paciente_b),
            servicos.ocorrencias(SEGUNDA, datetime.time(9), datetime.time(10)),
            None,
        )
    cliente = cenario["cliente"]
    eventos = cliente.get(
        reverse("agenda:eventos"),
        {"profissional": de_b.pk, "start": f"{SEGUNDA}T00:00:00", "end": f"{SEGUNDA}T23:00:00"},
    ).json()
    assert eventos == []
    assert cliente.get(reverse("agenda:editar", args=[agendamento_b.pk])).status_code == 404
    # Ids from another clinic are not accepted in the form either.
    resposta = agendar(cenario, profissional=de_b.pk, tipo=tipo_b.pk, paciente=paciente_b.pk)
    assert set(resposta.context["form"].errors) >= {"profissional", "tipo", "paciente"}


def cliente_da_dra_ana(cenario, criar_usuario, cliente_de):
    """A practitioner user linked to Dra. Ana's record."""
    usuario = criar_usuario("dra", cenario["clinica"], Papel.PROFISSIONAL)
    with usar_clinica(cenario["clinica"]):
        Profissional.objects.filter(pk=cenario["ana"].pk).update(usuario=usuario)
    return cliente_de(usuario)


def test_profissional_agenda_mas_nao_exclui(cenario, criar_usuario, cliente_de):
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)
    assert cliente.post(reverse("agenda:novo"), dados(cenario)).status_code == 204
    [agendamento] = agendamentos(cenario)
    assert cliente.post(reverse("agenda:excluir", args=[agendamento.pk])).status_code == 403
    formulario = cliente.get(reverse("agenda:editar", args=[agendamento.pk])).content.decode()
    assert "Excluir" not in formulario


def test_profissional_so_ve_a_propria_agenda(cenario, criar_usuario, cliente_de):
    assert agendar(cenario, profissional=cenario["bruno"].pk).status_code == 204
    [do_bruno] = agendamentos(cenario)
    # The front desk sees every practitioner (checked first: the test client is shared).
    resposta = cenario["cliente"].get(reverse("agenda:calendario"))
    assert len(resposta.context["profissionais"]) == 2
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)

    resposta = cliente.get(reverse("agenda:calendario"), {"profissional": cenario["bruno"].pk})
    assert [p.nome for p in resposta.context["profissionais"]] == ["Dra. Ana"]
    assert resposta.context["profissional"] == cenario["ana"]
    periodo = {"start": "2031-03-03T00:00:00", "end": "2031-03-10T00:00:00"}
    eventos = cliente.get(
        reverse("agenda:eventos"), {**periodo, "profissional": cenario["bruno"].pk}
    )
    assert eventos.json() == []
    assert cliente.get(reverse("agenda:editar", args=[do_bruno.pk])).status_code == 404

    resposta = cliente.post(
        reverse("agenda:novo"),
        dados(cenario, profissional=cenario["bruno"].pk, hora_inicio="11:00", hora_fim="12:00"),
    )
    assert resposta.status_code == 200
    assert "profissional" in resposta.context["form"].errors


def test_profissional_sem_cadastro_ligado_nao_ve_agenda(cenario, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("sem_cadastro", cenario["clinica"], Papel.PROFISSIONAL))
    resposta = cliente.get(reverse("agenda:calendario"))
    assert resposta.context["profissionais"] == []
    assert "não está ligado a um cadastro de profissional" in resposta.content.decode()


def test_sugestoes_de_pacientes_so_da_clinica(cenario, clinica_b):
    with usar_clinica(clinica_b):
        Paciente.objects.create(nome="Maria de Outra Clínica")
    conteudo = (
        cenario["cliente"].get(reverse("pacientes:sugestoes"), {"q": "maria"}).content.decode()
    )
    assert "Maria Paciente" in conteudo
    assert "Outra Clínica" not in conteudo


def test_filtro_da_clinica_e_decidido_na_execucao(clinica_a):
    # Building a queryset (e.g. form field choices at import time) must not fail...
    consulta = Agendamento.objects.filter(descricao="x")
    assert AgendamentoForm.base_fields["profissional"].queryset is not None
    # ...but running it without a current clinic must.
    with pytest.raises(SemClinicaAtual):
        list(consulta)
    with usar_clinica(clinica_a):
        assert list(consulta) == []


def test_periodo_com_e_sem_fuso_misturados(cenario):
    resposta = cenario["cliente"].get(
        reverse("agenda:eventos"),
        {
            "start": "2031-03-03T00:00:00",
            "end": "2031-03-10T00:00:00-03:00",
            "profissional": cenario["ana"].pk,
        },
    )
    assert resposta.status_code == 200


# --- Patient record history --------------------------------------------------------


def test_ficha_mostra_proximos_e_anteriores(cenario, criar_usuario, cliente_de):
    agora = timezone.localtime()
    passado = agora.date() - datetime.timedelta(days=7)
    with usar_clinica(cenario["clinica"]):
        Agendamento.objects.create(
            profissional=cenario["ana"],
            tipo=cenario["tipo"],
            paciente=cenario["paciente"],
            inicio=servicos.momento(passado, datetime.time(9)),
            fim=servicos.momento(passado, datetime.time(10)),
        )
    agendar(cenario)  # 2031, Dra. Ana
    agendar(cenario, profissional=cenario["bruno"].pk, hora_inicio="11:00", hora_fim="12:00")
    url = reverse("pacientes:ficha", args=[cenario["paciente"].pk])

    historico = cenario["cliente"].get(url).context["agendamentos"]
    assert historico["total"] == 3
    assert [a.profissional.nome for a in historico["proximos"]] == ["Dra. Ana", "Dr. Bruno"]
    assert [a.inicio.date() for a in historico["anteriores"]] == [passado]

    # Practitioners see only their own appointments in the record too.
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)
    resposta = cliente.get(url)
    historico = resposta.context["agendamentos"]
    assert historico["total"] == 2
    assert {a.profissional.nome for a in historico["proximos"]} == {"Dra. Ana"}
    assert "?profissional=" in resposta.content.decode()


# --- Simulated activity --------------------------------------------------------------


def test_simular_movimento_respeita_horarios_ocupados(cenario):
    # A real appointment today at 09:00 for Dra. Ana must stay untouched.
    hoje = timezone.localdate()
    with usar_clinica(cenario["clinica"]):
        Paciente.objects.create(nome="Arquivado", arquivado=True)
        existente = Agendamento.objects.create(
            profissional=cenario["ana"],
            tipo=cenario["tipo"],
            inicio=servicos.momento(hoje, datetime.time(9)),
            fim=servicos.momento(hoje, datetime.time(10)),
            descricao="Real",
        )
    with pytest.raises(CommandError):
        call_command("simular_movimento", clinica=cenario["clinica"].nome)
    call_command("simular_movimento", clinica=cenario["clinica"].nome, confirmar=True)

    with usar_clinica(cenario["clinica"]):
        novos = Agendamento.objects.exclude(pk=existente.pk)
        assert novos.count() > 0
        assert not novos.filter(
            profissional=cenario["ana"], inicio__lt=existente.fim, fim__gt=existente.inicio
        ).exists()
        assert not novos.filter(paciente__arquivado=True).exists()
        assert novos.filter(tipo__nome="Ocupado").count() == 0
        assert Rechamada.objects.count() == 80
        assert not Rechamada.objects.filter(paciente__arquivado=True).exists()
        # Cheques are not used anymore, not even in made-up data.
        assert Pagamento.objects.exists()
        assert not Pagamento.objects.filter(forma=Pagamento.Forma.CHEQUE).exists()


def test_simular_so_rechamadas(cenario):
    call_command(
        "simular_movimento",
        clinica=cenario["clinica"].nome,
        sem_agenda=True,
        rechamadas=5,
        confirmar=True,
    )
    with usar_clinica(cenario["clinica"]):
        assert not Agendamento.objects.exists()
        assert Rechamada.objects.count() == 5


# --- Came / missed / cancelled (0.24.0) ---------------------------------------------------


def agendamento_em(cenario, dia, hora=9, paciente=True, profissional="ana"):
    with usar_clinica(cenario["clinica"]):
        return Agendamento.objects.create(
            profissional=cenario[profissional],
            tipo=cenario["tipo"],
            paciente=cenario["paciente"] if paciente else None,
            descricao="" if paciente else "Bloqueado",
            inicio=servicos.momento(dia, datetime.time(hora)),
            fim=servicos.momento(dia, datetime.time(hora + 1)),
        )


def marcar(cenario, agendamento, situacao, htmx=True, cliente=None):
    cabecalhos = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    return (cliente or cenario["cliente"]).post(
        reverse("agenda:situacao", args=[agendamento.pk]), {"situacao": situacao}, **cabecalhos
    )


def situacao_de(cenario, agendamento):
    with usar_clinica(cenario["clinica"]):
        return Agendamento.objects.get(pk=agendamento.pk).situacao


def test_marca_comparecimento_e_falta_a_partir_do_dia(cenario):
    hoje = timezone.localdate()
    agendamento = agendamento_em(cenario, hoje)
    resposta = marcar(cenario, agendamento, "compareceu")
    assert resposta.status_code == 204
    assert json.loads(resposta["HX-Trigger"]) == {
        "agendaAtualizada": {"mensagem": "Maria Paciente compareceu."}
    }
    assert situacao_de(cenario, agendamento) == "compareceu"
    assert marcar(cenario, agendamento, "agendado").status_code == 204
    assert situacao_de(cenario, agendamento) == "agendado"

    # The appointment window shows the buttons; a future one only offers "cancelled".
    janela = cenario["cliente"].get(reverse("agenda:editar", args=[agendamento.pk]))
    assert "Compareceu" in janela.content.decode()
    futuro = agendamento_em(cenario, SEGUNDA)
    janela = cenario["cliente"].get(reverse("agenda:editar", args=[futuro.pk])).content.decode()
    assert '"situacao": "faltou"' not in janela and '"situacao": "desmarcou"' in janela
    resposta = marcar(cenario, futuro, "faltou")
    assert resposta.status_code == 200
    assert "a partir do dia do atendimento" in resposta.context["erro_situacao"]
    assert situacao_de(cenario, futuro) == "agendado"


def test_situacao_invalida_e_horario_sem_paciente_sao_recusados(cenario):
    hoje = timezone.localdate()
    bloqueio = agendamento_em(cenario, hoje, paciente=False)
    resposta = marcar(cenario, bloqueio, "compareceu", htmx=False)
    assert resposta.status_code == 302 and resposta.url == reverse("inicio")
    assert situacao_de(cenario, bloqueio) == "agendado"
    agendamento = agendamento_em(cenario, hoje, hora=11)
    marcar(cenario, agendamento, "chegou")
    assert situacao_de(cenario, agendamento) == "agendado"
    assert (
        cenario["cliente"].get(reverse("agenda:situacao", args=[agendamento.pk])).status_code == 405
    )


def test_desmarcado_libera_o_horario(cenario):
    agendar(cenario)
    [primeiro] = agendamentos(cenario)
    assert marcar(cenario, primeiro, "desmarcou").status_code == 204
    # The slot is free again for another patient, also for the database constraint.
    assert agendar(cenario).status_code == 204
    assert len(agendamentos(cenario)) == 2
    # Undoing the cancellation would double-book: refused.
    resposta = marcar(cenario, primeiro, "agendado")
    assert "já foi ocupado" in resposta.context["erro_situacao"]
    assert situacao_de(cenario, primeiro) == "desmarcou"
    # Editing the cancelled one does not conflict with the new one either.
    resposta = cenario["cliente"].post(
        reverse("agenda:editar", args=[primeiro.pk]), dados(cenario, descricao="Remarcar")
    )
    assert resposta.status_code == 204


def test_remarcar_para_o_futuro_ou_tirar_o_paciente_limpa_a_presenca(cenario):
    hoje = timezone.localdate()
    agendamento = agendamento_em(cenario, hoje)
    marcar(cenario, agendamento, "faltou")
    resposta = cenario["cliente"].post(
        reverse("agenda:editar", args=[agendamento.pk]), dados(cenario)
    )
    assert resposta.status_code == 204
    assert situacao_de(cenario, agendamento) == "agendado"

    outro = agendamento_em(cenario, hoje, hora=11)
    marcar(cenario, outro, "compareceu")
    sem_paciente = dados(
        cenario,
        paciente="",
        descricao="Bloqueado",
        data=hoje.isoformat(),
        hora_inicio="11:00",
        hora_fim="12:00",
    )
    cenario["cliente"].post(reverse("agenda:editar", args=[outro.pk]), sem_paciente)
    assert situacao_de(cenario, outro) == "agendado"


def test_profissional_so_marca_a_propria_agenda(cenario, criar_usuario, cliente_de):
    hoje = timezone.localdate()
    do_bruno = agendamento_em(cenario, hoje, profissional="bruno")
    da_ana = agendamento_em(cenario, hoje)
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)
    assert marcar(cenario, do_bruno, "compareceu", cliente=cliente).status_code == 404
    assert marcar(cenario, da_ana, "compareceu", cliente=cliente).status_code == 204


def test_eventos_trazem_a_situacao(cenario):
    agendamento = agendamento_em(cenario, timezone.localdate())
    marcar(cenario, agendamento, "faltou")
    hoje = timezone.localdate()
    resposta = cenario["cliente"].get(
        reverse("agenda:eventos"),
        {
            "profissional": cenario["ana"].pk,
            "start": hoje.isoformat(),
            "end": (hoje + datetime.timedelta(days=1)).isoformat(),
        },
    )
    [evento] = resposta.json()
    assert evento["classNames"] == ["situacao-faltou"]
    assert evento["extendedProps"]["situacao_nome"] == "Faltou"
