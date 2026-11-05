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
        fields = rotulos.setdefault(nome_do_modelo(model), {})
        for field in model._meta.concrete_fields:
            for name in {field.column, field.column.removesuffix("_id"), field.attname, field.name}:
                fields[name] = field.verbose_name
    return rotulos


def campos_alterados(record):
    """The entry's changes as (label, before, after), in the user's language. A field the
    model no longer has (or "senha") shows its stored name."""
    rotulos = _rotulos().get(record.model_name, {})
    return [
        (rotulos.get(field, field), valores[0], valores[1])
        for field, valores in record.changes.items()
    ]


@exige_permissao(Modulo.AUDITORIA, Acao.VER)
def results(request):
    # Always restricted to the current clinic: this model is not auto-isolated.
    registros = AuditEntry.objects.filter(clinic=request.clinic)
    filters = {
        "q": request.GET.get("q", "").strip(),
        "action": request.GET.get("action", ""),
        "model_name": request.GET.get("model_name", ""),
        "de": request.GET.get("de", ""),
        "until": request.GET.get("until", ""),
    }
    modelos = tipos_de_registro()
    if filters["q"]:
        registros = registros.filter(
            Q(user_name__icontains=filters["q"])
            | Q(object_repr__icontains=filters["q"])
            | Q(object_id=filters["q"])
        )
    if filters["action"] in AuditEntry.Acao.values:
        registros = registros.filter(action=filters["action"])
    if filters["model_name"]:
        registros = registros.filter(model_name=filters["model_name"])
    if since := _data(filters["de"]):
        registros = registros.filter(timestamp__date__gte=since)
    if until := _data(filters["until"]):
        registros = registros.filter(timestamp__date__lte=until)
    page = Paginator(registros, POR_PAGINA).get_page(request.GET.get("pagina"))
    for record in page:
        record.fields = campos_alterados(record)
    return render(
        request,
        "audit/list.html",
        {
            "pagina": page,
            "filtros": filters,
            "parametros": urlencode(filters),
            "acoes": AuditEntry.Acao.choices,
            "modelos": modelos,
        },
    )
