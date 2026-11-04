import datetime
import json

import pytest
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from apps.core.isolation import SemClinicaAtual, usar_clinica
from apps.core.models import Papel
from apps.finance.models import Payment
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.schedule import services
from apps.schedule.forms import AgendamentoForm
from apps.schedule.models import Appointment, AppointmentType

pytestmark = pytest.mark.django_db

# A Monday well in the future, so tests never depend on today's date.
SEGUNDA = datetime.date(2031, 3, 3)


@pytest.fixture
def cenario(clinica_a, criar_profissional, criar_usuario, cliente_de):
    """Clinic A with two practitioners, a type, a patient and a front desk user."""
    with usar_clinica(clinica_a):
        kind = AppointmentType.objects.get(name="Cirurgia")
        patient = Patient.objects.create(name="Maria Paciente")
    return {
        "clinic": clinica_a,
        "ana": criar_profissional(clinica_a, "Dra. Ana"),
        "bruno": criar_profissional(clinica_a, "Dr. Bruno"),
        "kind": kind,
        "patient": patient,
        "cliente": cliente_de(criar_usuario("recepcao", clinica_a, Papel.RECEPCAO)),
    }


def dados(cenario, **extra):
    return {
        "practitioner": cenario["ana"].pk,
        "kind": cenario["kind"].pk,
        "patient": cenario["patient"].pk,
        "description": "",
        "date": SEGUNDA.isoformat(),
        "hora_inicio": "09:00",
        "hora_fim": "10:00",
        "repeticoes": 1,
        **extra,
    }


def agendar(cenario, **extra):
    return cenario["cliente"].post(reverse("schedule:new"), dados(cenario, **extra))


def agendamentos(cenario):
    with usar_clinica(cenario["clinic"]):
        return list(Appointment.objects.order_by("inicio"))


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
    assert agendamento.patient == cenario["patient"]
    assert agendamento.created_by.username == "recepcao"
    assert agendamento.serie is None


def test_repeticao_semanal_cria_a_serie(cenario):
    assert agendar(cenario, repeticoes=4).status_code == 204
    criados = agendamentos(cenario)
    assert len(criados) == 4
    assert len({a.serie for a in criados}) == 1 and criados[0].serie is not None
    datas = [a.inicio.date() for a in criados]
    assert datas == [SEGUNDA + datetime.timedelta(weeks=n) for n in range(4)]


def test_sem_paciente_exige_descricao(cenario):
    resposta = agendar(cenario, patient="", description="")
    assert "Informe o paciente ou uma descrição" in erros(resposta)
    assert agendar(cenario, patient="", description="Reunião de equipe").status_code == 204
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
    clinic = cenario["clinic"]
    clinic.agenda_intervalo = 15
    clinic.save()
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
    assert agendar(cenario, practitioner=cenario["bruno"].pk).status_code == 204
    assert len(agendamentos(cenario)) == 4


def test_repeticao_com_conflito_nao_grava_nenhuma(cenario):
    terceira_semana = SEGUNDA + datetime.timedelta(weeks=2)
    agendar(cenario, date=terceira_semana.isoformat())
    resposta = agendar(cenario, repeticoes=4)
    assert resposta.status_code == 200
    assert terceira_semana.strftime("%d/%m") in erros(resposta)
    assert "Nada foi gravado" in erros(resposta)
    assert len(agendamentos(cenario)) == 1


def test_banco_de_dados_impede_sobreposicao(cenario):
    """Even bypassing the form (e.g. two simultaneous requests), the database refuses."""
    with usar_clinica(cenario["clinic"]):
        intervalos = services.ocorrencias(SEGUNDA, datetime.time(9), datetime.time(10))
        modelo = Appointment(
            practitioner=cenario["ana"], kind=cenario["kind"], description="Primeiro"
        )
        services.criar(modelo, intervalos, None)
        sobreposto = services.ocorrencias(SEGUNDA, datetime.time(9, 30), datetime.time(10, 30))
        with pytest.raises(IntegrityError), transaction.atomic():
            services.criar(modelo, sobreposto, None)


# --- Editing and deleting ----------------------------------------------------------


def test_editar_muda_o_horario_sem_conflitar_consigo_mesmo(cenario):
    agendar(cenario)
    [agendamento] = agendamentos(cenario)
    url = reverse("schedule:edit", args=[agendamento.pk])
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
    cliente.post(reverse("schedule:status", args=[agendamento.pk]), {"status": "desmarcou"})
    janela = cliente.get(reverse("schedule:edit", args=[agendamento.pk])).content.decode()
    assert "Agendar outro paciente neste horário" in janela
    assert (
        f"{reverse('schedule:new')}?practitioner={cenario['ana'].pk}&amp;date={SEGUNDA}" in janela
    )
    with usar_clinica(cenario["clinic"]):
        outro = Patient.objects.create(name="Outro Paciente")
    troca = cliente.post(
        reverse("schedule:edit", args=[agendamento.pk]), dados(cenario, patient=outro.pk)
    )
    assert "patient" in troca.context["form"].errors
    novo = cliente.post(reverse("schedule:new"), dados(cenario, patient=outro.pk))
    assert novo.status_code == 204
    with usar_clinica(cenario["clinic"]):
        nomes = sorted((a.patient.name, a.status) for a in Appointment.objects.all())
    assert nomes == [("Maria Paciente", "desmarcou"), ("Outro Paciente", "agendado")]


def test_excluir_um_ou_a_serie_dali_em_diante(cenario, criar_usuario, cliente_de):
    agendar(cenario, repeticoes=4)
    criados = agendamentos(cenario)
    admin = cliente_de(criar_usuario("admin", cenario["clinic"], Papel.ADMIN))

    admin.post(reverse("schedule:delete", args=[criados[0].pk]), {"escopo": "este"})
    assert len(agendamentos(cenario)) == 3

    pagina = admin.get(reverse("schedule:delete", args=[criados[1].pk])).content.decode()
    assert "os próximos 2" in pagina
    resposta = admin.post(reverse("schedule:delete", args=[criados[1].pk]), {"escopo": "serie"})
    assert json.loads(resposta["HX-Trigger"])["agendaAtualizada"]["mensagem"] == (
        "3 agendamentos excluídos."
    )
    assert agendamentos(cenario) == []


def test_paciente_arquivado_some_das_sugestoes_mas_fica_na_agenda(
    cenario, criar_usuario, cliente_de
):
    agendar(cenario)
    with usar_clinica(cenario["clinic"]):
        Patient.objects.filter(pk=cenario["patient"].pk).update(arquivado=True)
    sugestoes = cenario["cliente"].get(reverse("patients:suggestions"), {"q": "maria"})
    assert "Maria Paciente" not in sugestoes.content.decode()
    periodo = {"start": "2031-03-03T00:00:00", "end": "2031-03-10T00:00:00"}
    eventos = cenario["cliente"].get(
        reverse("schedule:events"), {**periodo, "practitioner": cenario["ana"].pk}
    )
    assert [e["title"] for e in eventos.json()] == ["Maria Paciente"]  # history kept


def test_exclusao_definitiva_tira_o_paciente_dos_agendamentos(cenario, criar_usuario, cliente_de):
    agendar(cenario)
    admin = cliente_de(criar_usuario("admin", cenario["clinic"], Papel.ADMIN))
    patient = cenario["patient"]
    admin.post(reverse("patients:archive", args=[patient.pk]))
    assert admin.post(reverse("patients:delete", args=[patient.pk])).status_code == 302
    [agendamento] = agendamentos(cenario)
    assert agendamento.patient is None
    # The slot stays taken, without the notes (they may hold personal data).
    assert agendamento.description == f"Paciente excluído (código {patient.pk})"
    with usar_clinica(cenario["clinic"]):
        assert not Patient.objects.filter(pk=patient.pk).exists()


# --- Calendar feeds ----------------------------------------------------------------


def test_eventos_do_periodo_em_json(cenario):
    agendar(cenario)
    agendar(cenario, date=(SEGUNDA + datetime.timedelta(weeks=1)).isoformat())
    resposta = cenario["cliente"].get(
        reverse("schedule:events"),
        {
            "practitioner": cenario["ana"].pk,
            "start": f"{SEGUNDA}T00:00:00-03:00",
            "end": f"{SEGUNDA + datetime.timedelta(days=7)}T00:00:00-03:00",
        },
    )
    [evento] = resposta.json()
    assert evento["title"] == "Maria Paciente"
    assert evento["start"].startswith(f"{SEGUNDA}T09:00:00")
    assert evento["backgroundColor"] == "#f7a5a5"
    assert evento["extendedProps"]["kind"] == "Cirurgia"


def test_eventos_com_parametros_invalidos(cenario):
    url = reverse("schedule:events")
    assert cenario["cliente"].get(url, {"practitioner": "x"}).status_code == 400
    longo = {"practitioner": 1, "start": "2031-01-01", "end": "2031-12-31"}
    assert cenario["cliente"].get(url, longo).status_code == 400


def test_aniversariantes_no_periodo(cenario):
    with usar_clinica(cenario["clinic"]):
        Patient.objects.create(name="Aniversariante", data_nascimento=datetime.date(1990, 3, 5))
        Patient.objects.create(
            name="Inativo", data_nascimento=datetime.date(1990, 3, 5), active=False
        )
    resposta = cenario["cliente"].get(
        reverse("schedule:birthdays"),
        {"start": f"{SEGUNDA}T00:00:00", "end": f"{SEGUNDA + datetime.timedelta(days=7)}T00:00:00"},
    )
    assert resposta.json() == {"2031-03-05": 1}
    lista = cenario["cliente"].get(reverse("schedule:birthdays_today"), {"date": "2031-03-05"})
    assert "Aniversariante" in lista.content.decode()
    assert "completa 41 anos" in lista.content.decode()


def test_calendario_abre_no_profissional_escolhido(cenario):
    pagina = cenario["cliente"].get(
        reverse("schedule:calendar"), {"practitioner": cenario["bruno"].pk}
    )
    assert pagina.context["practitioner"] == cenario["bruno"]
    config = pagina.context["configuracao"]
    assert config["intervalo"] == 30 and config["inicio"] == "07:30:00"
    assert config["pode"] == {"criar": True, "alterar": True}
    # The choice is remembered for the next visit.
    assert (
        cenario["cliente"].get(reverse("schedule:calendar")).context["practitioner"]
        == cenario["bruno"]
    )


# --- Isolation and permissions -----------------------------------------------------


def test_agenda_de_outra_clinica_e_invisivel(cenario, clinica_b, criar_profissional):
    de_b = criar_profissional(clinica_b, "Dr. B")
    with usar_clinica(clinica_b):
        tipo_b = AppointmentType.objects.get(name="Cirurgia")
        paciente_b = Patient.objects.create(name="Paciente B")
        [agendamento_b] = services.criar(
            Appointment(practitioner=de_b, kind=tipo_b, patient=paciente_b),
            services.ocorrencias(SEGUNDA, datetime.time(9), datetime.time(10)),
            None,
        )
    cliente = cenario["cliente"]
    eventos = cliente.get(
        reverse("schedule:events"),
        {"practitioner": de_b.pk, "start": f"{SEGUNDA}T00:00:00", "end": f"{SEGUNDA}T23:00:00"},
    ).json()
    assert eventos == []
    assert cliente.get(reverse("schedule:edit", args=[agendamento_b.pk])).status_code == 404
    # Ids from another clinic are not accepted in the form either.
    resposta = agendar(cenario, practitioner=de_b.pk, kind=tipo_b.pk, patient=paciente_b.pk)
    assert set(resposta.context["form"].errors) >= {"practitioner", "kind", "patient"}


def cliente_da_dra_ana(cenario, criar_usuario, cliente_de):
    """A practitioner user linked to Dra. Ana's record."""
    user = criar_usuario("dra", cenario["clinic"], Papel.PROFISSIONAL)
    with usar_clinica(cenario["clinic"]):
        Practitioner.objects.filter(pk=cenario["ana"].pk).update(user=user)
    return cliente_de(user)


def test_profissional_agenda_mas_nao_exclui(cenario, criar_usuario, cliente_de):
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)
    assert cliente.post(reverse("schedule:new"), dados(cenario)).status_code == 204
    [agendamento] = agendamentos(cenario)
    assert cliente.post(reverse("schedule:delete", args=[agendamento.pk])).status_code == 403
    formulario = cliente.get(reverse("schedule:edit", args=[agendamento.pk])).content.decode()
    assert "Excluir" not in formulario


def test_profissional_so_ve_a_propria_agenda(cenario, criar_usuario, cliente_de):
    assert agendar(cenario, practitioner=cenario["bruno"].pk).status_code == 204
    [do_bruno] = agendamentos(cenario)
    # The front desk sees every practitioner (checked first: the test client is shared).
    resposta = cenario["cliente"].get(reverse("schedule:calendar"))
    assert len(resposta.context["profissionais"]) == 2
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)

    resposta = cliente.get(reverse("schedule:calendar"), {"practitioner": cenario["bruno"].pk})
    assert [p.name for p in resposta.context["profissionais"]] == ["Dra. Ana"]
    assert resposta.context["practitioner"] == cenario["ana"]
    periodo = {"start": "2031-03-03T00:00:00", "end": "2031-03-10T00:00:00"}
    eventos = cliente.get(
        reverse("schedule:events"), {**periodo, "practitioner": cenario["bruno"].pk}
    )
    assert eventos.json() == []
    assert cliente.get(reverse("schedule:edit", args=[do_bruno.pk])).status_code == 404

    resposta = cliente.post(
        reverse("schedule:new"),
        dados(cenario, practitioner=cenario["bruno"].pk, hora_inicio="11:00", hora_fim="12:00"),
    )
    assert resposta.status_code == 200
    assert "practitioner" in resposta.context["form"].errors


def test_profissional_sem_cadastro_ligado_nao_ve_agenda(cenario, criar_usuario, cliente_de):
    cliente = cliente_de(criar_usuario("sem_cadastro", cenario["clinic"], Papel.PROFISSIONAL))
    resposta = cliente.get(reverse("schedule:calendar"))
    assert resposta.context["profissionais"] == []
    assert "não está ligado a um cadastro de profissional" in resposta.content.decode()


def test_sugestoes_de_pacientes_so_da_clinica(cenario, clinica_b):
    with usar_clinica(clinica_b):
        Patient.objects.create(name="Maria de Outra Clínica")
    conteudo = (
        cenario["cliente"].get(reverse("patients:suggestions"), {"q": "maria"}).content.decode()
    )
    assert "Maria Paciente" in conteudo
    assert "Outra Clínica" not in conteudo


def test_filtro_da_clinica_e_decidido_na_execucao(clinica_a):
    # Building a queryset (e.g. form field choices at import time) must not fail...
    consulta = Appointment.objects.filter(description="x")
    assert AgendamentoForm.base_fields["practitioner"].queryset is not None
    # ...but running it without a current clinic must.
    with pytest.raises(SemClinicaAtual):
        list(consulta)
    with usar_clinica(clinica_a):
        assert list(consulta) == []


def test_periodo_com_e_sem_fuso_misturados(cenario):
    resposta = cenario["cliente"].get(
        reverse("schedule:events"),
        {
            "start": "2031-03-03T00:00:00",
            "end": "2031-03-10T00:00:00-03:00",
            "practitioner": cenario["ana"].pk,
        },
    )
    assert resposta.status_code == 200


# --- Patient record history --------------------------------------------------------


def test_ficha_mostra_proximos_e_anteriores(cenario, criar_usuario, cliente_de):
    agora = timezone.localtime()
    passado = agora.date() - datetime.timedelta(days=7)
    with usar_clinica(cenario["clinic"]):
        Appointment.objects.create(
            practitioner=cenario["ana"],
            kind=cenario["kind"],
            patient=cenario["patient"],
            inicio=services.momento(passado, datetime.time(9)),
            fim=services.momento(passado, datetime.time(10)),
        )
    agendar(cenario)  # 2031, Dra. Ana
    agendar(cenario, practitioner=cenario["bruno"].pk, hora_inicio="11:00", hora_fim="12:00")
    url = reverse("patients:record", args=[cenario["patient"].pk])

    historico = cenario["cliente"].get(url).context["agendamentos"]
    assert historico["total"] == 3
    assert [a.practitioner.name for a in historico["proximos"]] == ["Dra. Ana", "Dr. Bruno"]
    assert [a.inicio.date() for a in historico["anteriores"]] == [passado]

    # Practitioners see only their own appointments in the record too.
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)
    resposta = cliente.get(url)
    historico = resposta.context["agendamentos"]
    assert historico["total"] == 2
    assert {a.practitioner.name for a in historico["proximos"]} == {"Dra. Ana"}
    assert "?practitioner=" in resposta.content.decode()


# --- Simulated activity --------------------------------------------------------------


def test_simular_movimento_respeita_horarios_ocupados(cenario):
    # A real appointment today at 09:00 for Dra. Ana must stay untouched.
    hoje = timezone.localdate()
    with usar_clinica(cenario["clinic"]):
        Patient.objects.create(name="Arquivado", arquivado=True)
        existente = Appointment.objects.create(
            practitioner=cenario["ana"],
            kind=cenario["kind"],
            inicio=services.momento(hoje, datetime.time(9)),
            fim=services.momento(hoje, datetime.time(10)),
            description="Real",
        )
    with pytest.raises(CommandError):
        call_command("simulate_activity", clinic=cenario["clinic"].name)
    call_command("simulate_activity", clinic=cenario["clinic"].name, confirmar=True)

    with usar_clinica(cenario["clinic"]):
        novos = Appointment.objects.exclude(pk=existente.pk)
        assert novos.count() > 0
        assert not novos.filter(
            practitioner=cenario["ana"], inicio__lt=existente.fim, fim__gt=existente.inicio
        ).exists()
        assert not novos.filter(patient__arquivado=True).exists()
        assert novos.filter(kind__name="Ocupado").count() == 0
        assert Recall.objects.count() == 80
        assert not Recall.objects.filter(patient__arquivado=True).exists()
        # Cheques are not used anymore, not even in made-up data.
        assert Payment.objects.exists()
        assert not Payment.objects.filter(forma=Payment.Forma.CHEQUE).exists()


def test_simular_so_rechamadas(cenario):
    call_command(
        "simulate_activity",
        clinic=cenario["clinic"].name,
        sem_agenda=True,
        rechamadas=5,
        confirmar=True,
    )
    with usar_clinica(cenario["clinic"]):
        assert not Appointment.objects.exists()
        assert Recall.objects.count() == 5


# --- Came / missed / cancelled (0.24.0) ---------------------------------------------------


def agendamento_em(cenario, dia, hora=9, patient=True, practitioner="ana"):
    with usar_clinica(cenario["clinic"]):
        return Appointment.objects.create(
            practitioner=cenario[practitioner],
            kind=cenario["kind"],
            patient=cenario["patient"] if patient else None,
            description="" if patient else "Bloqueado",
            inicio=services.momento(dia, datetime.time(hora)),
            fim=services.momento(dia, datetime.time(hora + 1)),
        )


def marcar(cenario, agendamento, status, htmx=True, cliente=None):
    cabecalhos = {"HTTP_HX_REQUEST": "true"} if htmx else {}
    return (cliente or cenario["cliente"]).post(
        reverse("schedule:status", args=[agendamento.pk]), {"status": status}, **cabecalhos
    )


def situacao_de(cenario, agendamento):
    with usar_clinica(cenario["clinic"]):
        return Appointment.objects.get(pk=agendamento.pk).status


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
    janela = cenario["cliente"].get(reverse("schedule:edit", args=[agendamento.pk]))
    assert "Compareceu" in janela.content.decode()
    futuro = agendamento_em(cenario, SEGUNDA)
    janela = cenario["cliente"].get(reverse("schedule:edit", args=[futuro.pk])).content.decode()
    assert '"situacao": "faltou"' not in janela and '"situacao": "desmarcou"' in janela
    resposta = marcar(cenario, futuro, "faltou")
    assert resposta.status_code == 200
    assert "a partir do dia do atendimento" in resposta.context["erro_situacao"]
    assert situacao_de(cenario, futuro) == "agendado"


def test_situacao_invalida_e_horario_sem_paciente_sao_recusados(cenario):
    hoje = timezone.localdate()
    bloqueio = agendamento_em(cenario, hoje, patient=False)
    resposta = marcar(cenario, bloqueio, "compareceu", htmx=False)
    assert resposta.status_code == 302 and resposta.url == reverse("home")
    assert situacao_de(cenario, bloqueio) == "agendado"
    agendamento = agendamento_em(cenario, hoje, hora=11)
    marcar(cenario, agendamento, "chegou")
    assert situacao_de(cenario, agendamento) == "agendado"
    assert (
        cenario["cliente"].get(reverse("schedule:status", args=[agendamento.pk])).status_code == 405
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
        reverse("schedule:edit", args=[primeiro.pk]), dados(cenario, description="Remarcar")
    )
    assert resposta.status_code == 204


def test_remarcar_para_o_futuro_ou_tirar_o_paciente_limpa_a_presenca(cenario):
    hoje = timezone.localdate()
    agendamento = agendamento_em(cenario, hoje)
    marcar(cenario, agendamento, "faltou")
    resposta = cenario["cliente"].post(
        reverse("schedule:edit", args=[agendamento.pk]), dados(cenario)
    )
    assert resposta.status_code == 204
    assert situacao_de(cenario, agendamento) == "agendado"

    outro = agendamento_em(cenario, hoje, hora=11)
    marcar(cenario, outro, "compareceu")
    sem_paciente = dados(
        cenario,
        patient="",
        description="Bloqueado",
        date=hoje.isoformat(),
        hora_inicio="11:00",
        hora_fim="12:00",
    )
    cenario["cliente"].post(reverse("schedule:edit", args=[outro.pk]), sem_paciente)
    assert situacao_de(cenario, outro) == "agendado"


def test_profissional_so_marca_a_propria_agenda(cenario, criar_usuario, cliente_de):
    hoje = timezone.localdate()
    do_bruno = agendamento_em(cenario, hoje, practitioner="bruno")
    da_ana = agendamento_em(cenario, hoje)
    cliente = cliente_da_dra_ana(cenario, criar_usuario, cliente_de)
    assert marcar(cenario, do_bruno, "compareceu", cliente=cliente).status_code == 404
    assert marcar(cenario, da_ana, "compareceu", cliente=cliente).status_code == 204


def test_eventos_trazem_a_situacao(cenario):
    agendamento = agendamento_em(cenario, timezone.localdate())
    marcar(cenario, agendamento, "faltou")
    hoje = timezone.localdate()
    resposta = cenario["cliente"].get(
        reverse("schedule:events"),
        {
            "practitioner": cenario["ana"].pk,
            "start": hoje.isoformat(),
            "end": (hoje + datetime.timedelta(days=1)).isoformat(),
        },
    )
    [evento] = resposta.json()
    assert evento["classNames"] == ["situacao-faltou"]
    assert evento["extendedProps"]["status_name"] == "Faltou"


def test_tipos_padrao_aparecem_no_idioma_do_usuario(cenario):
    """The default types are saved in Portuguese and shown translated; a type the clinic
    typed itself is shown as saved."""
    cliente = cenario["cliente"]
    with usar_clinica(cenario["clinic"]):
        AppointmentType.objects.create(name="Clareamento a laser", cor="#ffffff")

    cliente.post(reverse("change_language"), {"idioma": "en"})
    legenda = cliente.get(reverse("schedule:calendar")).content.decode()
    assert ">Surgery<" in legenda and ">Orthodontics<" in legenda
    assert ">Cirurgia<" not in legenda
    assert ">Clareamento a laser<" in legenda
    assert ">Surgery</option>" in cliente.get(reverse("schedule:new")).content.decode()

    cliente.post(reverse("change_language"), {"idioma": "es"})
    assert ">Cirugía<" in cliente.get(reverse("schedule:calendar")).content.decode()
    with usar_clinica(cenario["clinic"]):
        assert AppointmentType.objects.filter(name="Cirurgia").exists()  # data untouched
