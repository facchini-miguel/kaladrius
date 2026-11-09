"""Writing audit entries. The request context (user, IP) comes from AuditoriaMiddleware."""

import contextlib
from contextvars import ContextVar

from django.conf import settings
from django.utils import translation

from apps.core.isolation import current_clinic, isolation_active

from . import events
from .models import AuditEntry

_user = ContextVar("auditoria_usuario", default=None)
_ip = ContextVar("auditoria_ip", default=None)


@contextlib.contextmanager
def context(user, ip):
    tokens = (_user.set(user), _ip.set(ip))
    try:
        yield
    finally:
        _user.reset(tokens[0])
        _ip.reset(tokens[1])


def request_ip(request):
    return request.META.get("REMOTE_ADDR") or None


def log_event(
    action,
    obj=None,
    *,
    clinic=None,
    changes=None,
    user=None,
    ip=None,
    description="",
    event="",
    values=None,
):
    """Write an entry. What the system describes itself goes as an `event` of
    events.TEXTS and its `values` (decision 206), shown in the reader's language; its text
    in the source language is the description kept for the search."""
    values = {key: str(value) for key, value in (values or {}).items()}
    if event:
        with translation.override(settings.LANGUAGE_CODE):
            description = str(events.TEXTS[event]) % {"model": "", **values}
    user = user if user is not None else _user.get()
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    if clinic is None and obj is not None:
        # Rows without a clinic of their own (user accounts) are filed under the clinic
        # where the change was made, so the clinic administrator sees it in the audit log.
        clinic = _clinic_of(obj) or (current_clinic() if isolation_active() else None)
    return AuditEntry.objects.create(
        action=action,
        clinic_id=getattr(clinic, "pk", clinic),
        user=user,
        user_name=user.get_username() if user else "",
        model_name=model_label(type(obj)) if obj is not None else "",
        object_id=str(obj.pk) if obj is not None and obj.pk is not None else "",
        object_repr=(description or (str(obj) if obj is not None else ""))[:200],
        changes=changes or {},
        event=event,
        event_values=values,
        ip=ip if ip is not None else _ip.get(),
    )


def model_label(model):
    """How entries name the kind of record ("Paciente", "Agendamento"...).

    Always in the source language, whatever the user's language: entries are filtered
    and anonymized by this name.
    """
    with translation.override(settings.LANGUAGE_CODE):
        return str(model._meta.verbose_name).capitalize()


def anonymize(model, ids):
    """Remove the personal data from the audit entries of these records (LGPD erasure).

    Who did what and when, the record code and the names of the changed fields stay;
    the values and the record description go, the event's values too.
    """
    name = model_label(model)
    records = AuditEntry.objects.filter(model_name=name, object_id__in=[str(i) for i in ids])
    removed = events.REMOVED
    for record in records:
        with translation.override(settings.LANGUAGE_CODE):
            record.object_repr = str(events.TEXTS[events.PERSONAL_DATA_REMOVED]) % {
                "model": name,
                "record": record.object_id,
            }
        record.event = events.PERSONAL_DATA_REMOVED
        record.event_values = {}
        record.changes = {field: [removed, removed] for field in record.changes}
        record.save(update_fields=["object_repr", "event", "event_values", "changes"])


def _clinic_of(obj):
    from apps.core.models import Clinic

    if isinstance(obj, Clinic):
        return obj.pk
    return getattr(obj, "clinic_id", None)
