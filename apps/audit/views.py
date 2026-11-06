import datetime
from functools import cache

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils.http import urlencode

from apps.core.permissions import Action, Module, requires_permission

from .models import AuditEntry
from .record import model_label

PER_PAGE = 100


def _date(value):
    try:
        return datetime.date.fromisoformat(value or "")
    except ValueError:
        return None


def record_types():
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

    from .signals import AUDITED

    documentos = [Visit, Addendum, Certificate, Prescription, ExamRequest, Attachment]
    return sorted({model_label(model) for model in [*AUDITED, *documentos]})


@cache
def _labels():
    """For each kind of record, its fields' labels by every name an entry may have stored:
    the field's name and column, and its Portuguese name from before decisions 160 to 171."""
    from .old_names import OLD_FIELD_NAMES
    from .signals import AUDITED

    rotulos = {}
    for model in AUDITED:
        fields = rotulos.setdefault(model_label(model), {})
        for field in model._meta.concrete_fields:
            for name in {field.column, field.column.removesuffix("_id"), field.attname, field.name}:
                fields[name] = field.verbose_name
        for old, name in OLD_FIELD_NAMES.get(model._meta.label, {}).items():
            fields.setdefault(old, model._meta.get_field(name).verbose_name)
    return rotulos


def changed_fields(record):
    """The entry's changes as (label, before, after), in the user's language. A field the
    model no longer has (or "senha") shows its stored name."""
    rotulos = _labels().get(record.model_name, {})
    return [
        (rotulos.get(field, field), valores[0], valores[1])
        for field, valores in record.changes.items()
    ]


@requires_permission(Module.AUDIT, Action.VIEW)
def audit_list(request):
    # Always restricted to the current clinic: this model is not auto-isolated.
    registros = AuditEntry.objects.filter(clinic=request.clinic)
    filters = {
        "q": request.GET.get("q", "").strip(),
        "action": request.GET.get("action", ""),
        "model_name": request.GET.get("model_name", ""),
        "since": request.GET.get("since", ""),
        "until": request.GET.get("until", ""),
    }
    modelos = record_types()
    if filters["q"]:
        registros = registros.filter(
            Q(user_name__icontains=filters["q"])
            | Q(object_repr__icontains=filters["q"])
            | Q(object_id=filters["q"])
        )
    if filters["action"] in AuditEntry.Action.values:
        registros = registros.filter(action=filters["action"])
    if filters["model_name"]:
        registros = registros.filter(model_name=filters["model_name"])
    if since := _date(filters["since"]):
        registros = registros.filter(timestamp__date__gte=since)
    if until := _date(filters["until"]):
        registros = registros.filter(timestamp__date__lte=until)
    page = Paginator(registros, PER_PAGE).get_page(request.GET.get("page"))
    for record in page:
        record.fields = changed_fields(record)
    return render(
        request,
        "audit/list.html",
        {
            "pagina": page,
            "filtros": filters,
            "parametros": urlencode(filters),
            "acoes": AuditEntry.Action.choices,
            "modelos": modelos,
        },
    )
