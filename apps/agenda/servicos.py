"""Scheduling rules: weekly recurrences and conflict detection."""

import datetime
import uuid

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Agendamento


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
    """Existing appointments of the practitioner that overlap any of the intervals."""
    sobreposicao = Q()
    for inicio, fim in intervalos:
        sobreposicao |= Q(inicio__lt=fim, fim__gt=inicio)
    existentes = Agendamento.objects.filter(sobreposicao, profissional=profissional)
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
