import datetime
from functools import cache

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils.http import urlencode

from apps.core.permissions import Acao, Modulo, exige_permissao

from .models import AuditEntry
from .record import nome_do_modelo

POR_PAGINA = 100


def _data(value):
    try:
        return datetime.date.fromisoformat(value or "")
    except ValueError:
        return None


def tipos_de_registro():
    """Kinds of record in the filter: the audited models and the medical record documents
    (logged by hand). Asking the database took most of the page's time once the log had
    hundreds of thousands of entries (volume test, decision 108)."""
    from apps.medical_records.models import (
        Addendum,
        Attachment,
        Certificate,
        ExamRequest,
        Prescription,
        Visit,
    )

    from .signals import AUDITADOS

    documentos = [Visit, Addendum, Certificate, Prescription, ExamRequest, Attachment]
    return sorted({nome_do_modelo(model) for model in [*AUDITADOS, *documentos]})


@cache
def _rotulos():
    """For each kind of record, its fields' labels by every name an entry may have stored:
    the field's name, and its column (the name before decision 155's renaming, which keeps
    the database columns)."""
    from .signals import AUDITADOS

    rotulos = {}
    for model in AUDITADOS:
        campos = rotulos.setdefault(nome_do_modelo(model), {})
        for campo in model._meta.concrete_fields:
            for name in {campo.column, campo.column.removesuffix("_id"), campo.attname, campo.name}:
                campos[name] = campo.verbose_name
    return rotulos


def campos_alterados(record):
    """The entry's changes as (label, before, after), in the user's language. A field the
    model no longer has (or "senha") shows its stored name."""
    rotulos = _rotulos().get(record.model_name, {})
    return [
        (rotulos.get(campo, campo), valores[0], valores[1])
        for campo, valores in record.changes.items()
    ]


@exige_permissao(Modulo.AUDITORIA, Acao.VER)
def lista(request):
    # Always restricted to the current clinic: this model is not auto-isolated.
    registros = AuditEntry.objects.filter(clinic=request.clinic)
    filtros = {
        "q": request.GET.get("q", "").strip(),
        "action": request.GET.get("action", ""),
        "model_name": request.GET.get("model_name", ""),
        "de": request.GET.get("de", ""),
        "until": request.GET.get("until", ""),
    }
    modelos = tipos_de_registro()
    if filtros["q"]:
        registros = registros.filter(
            Q(user_name__icontains=filtros["q"])
            | Q(object_repr__icontains=filtros["q"])
            | Q(object_id=filtros["q"])
        )
    if filtros["action"] in AuditEntry.Acao.values:
        registros = registros.filter(action=filtros["action"])
    if filtros["model_name"]:
        registros = registros.filter(model_name=filtros["model_name"])
    if de := _data(filtros["de"]):
        registros = registros.filter(timestamp__date__gte=de)
    if until := _data(filtros["until"]):
        registros = registros.filter(timestamp__date__lte=until)
    pagina = Paginator(registros, POR_PAGINA).get_page(request.GET.get("pagina"))
    for record in pagina:
        record.campos = campos_alterados(record)
    return render(
        request,
        "audit/list.html",
        {
            "pagina": pagina,
            "filtros": filtros,
            "parametros": urlencode(filtros),
            "acoes": AuditEntry.Acao.choices,
            "modelos": modelos,
        },
    )
