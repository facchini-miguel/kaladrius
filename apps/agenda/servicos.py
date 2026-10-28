"""Scheduling rules: weekly recurrences and conflict detection."""

import datetime
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.core.permissoes import so_a_propria_agenda
from apps.profissionais.models import Profissional

from .models import Agendamento


def profissionais_visiveis(request):
    """Practitioners whose schedule the user may see and change (decision 044)."""
    if so_a_propria_agenda(request):
        return Profissional.objects.filter(usuario=request.user)
    return Profissional.objects.all()


def agendamentos_visiveis(request):
    return Agendamento.objects.filter(profissional__in=profissionais_visiveis(request))


def momento(data, hora):
    """Aware datetime for a local date and time."""
    return timezone.make_aware(datetime.datetime.combine(data, hora))


def ocorrencias(data, hora_inicio, hora_fim, repeticoes=1):
    """(start, end) of each weekly occurrence, built from local date/time (DST-safe)."""
    return [
        (momento(dia, hora_inicio), momento(dia, hora_fim))
        for dia in (data + datetime.timedelta(weeks=semana) for semana in range(repeticoes))
    ]


def conflitos(profissional, intervalos, ignorar=None):
    """Existing appointments of the practitioner that overlap any of the intervals.

    Cancelled ones (desmarcados) do not hold the slot.
    """
    sobreposicao = Q()
    for inicio, fim in intervalos:
        sobreposicao |= Q(inicio__lt=fim, fim__gt=inicio)
    existentes = Agendamento.objects.filter(sobreposicao, profissional=profissional).exclude(
        situacao=Agendamento.Situacao.DESMARCOU
    )
    if ignorar is not None:
        existentes = existentes.exclude(pk=ignorar)
    return list(existentes.select_related("paciente").order_by("inicio"))


@transaction.atomic
def criar(modelo, intervalos, usuario):
    """Create one appointment per interval, copying the fields of `modelo`.

    Raises IntegrityError if the database constraint finds an overlap (for example,
    another user booked the same slot a moment earlier); nothing is saved then.
    """
    serie = uuid.uuid4() if len(intervalos) > 1 else None
    criados = []
    for inicio, fim in intervalos:
        agendamento = Agendamento(
            profissional=modelo.profissional,
            tipo=modelo.tipo,
            paciente=modelo.paciente,
            descricao=modelo.descricao,
            inicio=inicio,
            fim=fim,
            serie=serie,
            criado_por=usuario,
        )
        agendamento.save()
        criados.append(agendamento)
    return criados


@transaction.atomic
def marcar(agendamento, situacao):
    """Record whether the patient came, missed or cancelled (0.24.0).

    Came or missed only from the day of the appointment on. Leaving "cancelled" takes the
    slot back, so it is refused if another appointment took it meanwhile.
    """
    if situacao not in Agendamento.Situacao.values:
        raise ValidationError(_("Situação inválida."))
    if agendamento.paciente_id is None:
        raise ValidationError(_("Só agendamentos com paciente têm situação."))
    presenca = (Agendamento.Situacao.COMPARECEU, Agendamento.Situacao.FALTOU)
    if situacao in presenca and not agendamento.presenca_marcavel:
        raise ValidationError(
            _("Comparecimento e falta só podem ser marcados a partir do dia do atendimento.")
        )
    ocupado = _("Este horário já foi ocupado por outro agendamento. Desmarque aquele antes.")
    if agendamento.desmarcado and situacao != Agendamento.Situacao.DESMARCOU:
        if conflitos(
            agendamento.profissional, [(agendamento.inicio, agendamento.fim)], agendamento.pk
        ):
            raise ValidationError(ocupado)
    agendamento.situacao = situacao
    try:
        with transaction.atomic():
            agendamento.save(update_fields=["situacao", "alterado_em"])
    except IntegrityError:
        raise ValidationError(ocupado) from None
    return agendamento
