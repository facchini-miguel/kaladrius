"""Writing audit entries. The request context (user, IP) comes from AuditoriaMiddleware."""

import contextlib
from contextvars import ContextVar

from django.conf import settings
from django.utils import translation

from apps.core.isolation import current_clinic, isolation_active

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


def log_event(action, obj=None, *, clinic=None, changes=None, user=None, ip=None, description=""):
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
        ip=ip if ip is not None else _ip.get(),
    )


def model_label(model):
    """How entries name the kind of record ("Paciente", "Agendamento"...).

    Always in the source language, whatever the user's language: entries are filtered
    and anonymized by this name.
    """
    with translation.override(settings.LANGUAGE_CODE):
        return str(model._meta.verbose_name).capitalize()


REMOVED = "(removido)"


def anonymize(model, ids):
    """Remove the personal data from the audit entries of these records (LGPD erasure).

    Who did what and when, the record code and the names of the changed fields stay;
    the values and the record description go.
    """
    name = model_label(model)
    records = AuditEntry.objects.filter(model_name=name, object_id__in=[str(i) for i in ids])
    for record in records:
        record.object_repr = f"{name} {record.object_id} (dados removidos)"
        record.changes = {field: [REMOVED, REMOVED] for field in record.changes}
        record.save(update_fields=["object_repr", "changes"])


def _clinic_of(obj):
    from apps.core.models import Clinic

    if isinstance(obj, Clinic):
        return obj.pk
    return getattr(obj, "clinic_id", None)
