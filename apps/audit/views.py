import datetime
from functools import cache

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils.http import urlencode

from apps.core.permissions import Action, Module, requires_permission
from apps.core.values import VALUES, code_value

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

    documents = [Visit, Addendum, Certificate, Prescription, ExamRequest, Attachment]
    return sorted({model_label(model) for model in [*AUDITED, *documents]})


@cache
def _labels():
    """For each kind of record, its fields' labels by every name an entry may have stored:
    the field's name and column, and its Portuguese name from before decisions 160 to 171."""
    from .old_names import OLD_FIELD_NAMES
    from .signals import AUDITED

    labels = {}
    for model in AUDITED:
        fields = labels.setdefault(model_label(model), {})
        for field in model._meta.concrete_fields:
            for name in {field.column, field.column.removesuffix("_id"), field.attname, field.name}:
                fields[name] = field.verbose_name
        for old, name in OLD_FIELD_NAMES.get(model._meta.label, {}).items():
            fields.setdefault(old, model._meta.get_field(name).verbose_name)
    return labels


@cache
def _choices():
    """For each kind of record, by every name an entry may have stored, its choice fields as
    (field key in VALUES, {code: label}): an entry shows "Compareceu", not the code it stored."""
    from .old_names import OLD_FIELD_NAMES
    from .signals import AUDITED

    choices = {}
    for model in AUDITED:
        fields = choices.setdefault(model_label(model), {})
        old_names = OLD_FIELD_NAMES.get(model._meta.label, {})
        for field in model._meta.concrete_fields:
            if not field.choices:
                continue
            shown = (f"{model._meta.label}.{field.name}", dict(field.choices))
            names = {field.column, field.attname, field.name}
            names |= {old for old, name in old_names.items() if name == field.name}
            for name in names:
                fields[name] = shown
    return choices


def _shown(choice, value):
    """A stored code as its label, in either spelling of decision 197."""
    if choice is None or not isinstance(value, str):
        return value
    key, labels = choice
    if key in VALUES:
        value = code_value(key, value)
    return labels.get(value, value)


def changed_fields(record):
    """The entry's changes as (label, before, after), in the user's language. A field the
    model no longer has (or "senha") shows its stored name."""
    labels = _labels().get(record.model_name, {})
    choices = _choices().get(record.model_name, {})
    return [
        (
            labels.get(field, field),
            _shown(choices.get(field), values[0]),
            _shown(choices.get(field), values[1]),
        )
        for field, values in record.changes.items()
    ]


@requires_permission(Module.AUDIT, Action.VIEW)
def audit_list(request):
    # Always restricted to the current clinic: this model is not auto-isolated.
    records = AuditEntry.objects.filter(clinic=request.clinic)
    filters = {
        "q": request.GET.get("q", "").strip(),
        "action": request.GET.get("action", ""),
        "model_name": request.GET.get("model_name", ""),
        "since": request.GET.get("since", ""),
        "until": request.GET.get("until", ""),
    }
    model_list = record_types()
    if filters["q"]:
        records = records.filter(
            Q(user_name__icontains=filters["q"])
            | Q(object_repr__icontains=filters["q"])
            | Q(object_id=filters["q"])
        )
    if filters["action"] in AuditEntry.Action.values:
        records = records.filter(action=filters["action"])
    if filters["model_name"]:
        records = records.filter(model_name=filters["model_name"])
    if since := _date(filters["since"]):
        records = records.filter(timestamp__date__gte=since)
    if until := _date(filters["until"]):
        records = records.filter(timestamp__date__lte=until)
    page = Paginator(records, PER_PAGE).get_page(request.GET.get("page"))
    for record in page:
        record.fields = changed_fields(record)
    return render(
        request,
        "audit/list.html",
        {
            "page": page,
            "filters": filters,
            "query": urlencode(filters),
            "actions": AuditEntry.Action.choices,
            "model_names": model_list,
        },
    )
