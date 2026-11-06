"""Automatic audit of creations, changes and deletions, plus logins."""

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_delete, post_save, pre_save

from apps.core.models import Clinic, ClinicModule, Membership
from apps.estimates.models import Estimate, EstimateItem, Procedure
from apps.finance.models import (
    AccountGroup,
    BankTransaction,
    BookClosing,
    CashMovement,
    CashRegister,
    Category,
    Commission,
    CostCenter,
    Entry,
    FinancialAccount,
    Installment,
    Payment,
    Planning,
    StatementImport,
    Supplier,
)
from apps.health_plans.models import HealthPlan, MemberCard
from apps.patients.models import Patient, RelatedPerson
from apps.practitioners.models import Practitioner
from apps.recalls.models import Recall
from apps.schedule.models import Appointment, AppointmentType
from apps.staff.models import Employee, Payroll, Salary

from .models import AuditEntry
from .record import log_event, request_ip

Action = AuditEntry.Action
User = get_user_model()

AUDITED = [
    Patient,
    Appointment,
    Recall,
    HealthPlan,
    MemberCard,
    RelatedPerson,
    Practitioner,
    AppointmentType,
    Clinic,
    ClinicModule,
    Membership,
    User,
    Supplier,
    Entry,
    Installment,
    Payment,
    FinancialAccount,
    Category,
    AccountGroup,
    Planning,
    Employee,
    Salary,
    Payroll,
    CostCenter,
    BookClosing,
    CashRegister,
    CashMovement,
    Commission,
    StatementImport,
    BankTransaction,
    Procedure,
    Estimate,
    EstimateItem,
]
# Never stored (secrets) or not worth storing (bookkeeping timestamps).
IGNORED = {
    "password",
    "last_login",
    "created_at",
    "updated_at",
    "last_seen_version",
    "language",
}


def _campos(model):
    return [
        field
        for field in model._meta.concrete_fields
        if not field.primary_key and field.attname not in IGNORED and field.name not in IGNORED
    ]


def _value(field, instance):
    value = field.value_from_object(instance)
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def _values(instance):
    return {field.name: _value(field, instance) for field in _campos(type(instance))}


def before_save(sender, instance, raw=False, **kwargs):
    if raw or instance.pk is None:
        instance._auditoria_antes = None
        return
    previous = sender._base_manager.filter(pk=instance.pk).first()
    instance._auditoria_antes = _values(previous) if previous is not None else None
    instance._password_audit = getattr(previous, "password", None)


def after_save(sender, instance, created, raw=False, update_fields=None, **kwargs):
    if raw:
        return
    after = _values(instance)
    before = getattr(instance, "_auditoria_antes", None)
    if created or before is None:
        changes = {
            field: [None, value] for field, value in after.items() if value not in (None, "")
        }
        log_event(Action.CREATE, instance, changes=changes)
        return
    changes = {
        field: [before.get(field), value]
        for field, value in after.items()
        if before.get(field) != value
    }
    if getattr(instance, "_password_audit", None) not in (
        None,
        getattr(instance, "password", None),
    ):
        changes["senha"] = ["(oculta)", "(alterada)"]  # the hash itself is never stored
    if changes:
        log_event(Action.CHANGE, instance, changes=changes)


def after_delete(sender, instance, **kwargs):
    values = {
        field: [value, None]
        for field, value in _values(instance).items()
        if value not in (None, "")
    }
    log_event(Action.DELETE, instance, changes=values)


for model in AUDITED:
    uid = f"auditoria_{model._meta.label_lower}"
    pre_save.connect(before_save, sender=model, dispatch_uid=f"{uid}_pre")
    post_save.connect(after_save, sender=model, dispatch_uid=f"{uid}_post")
    post_delete.connect(after_delete, sender=model, dispatch_uid=f"{uid}_delete")


def _logged_in(sender, request, user, **kwargs):
    log_event(Action.LOGIN, user=user, ip=request_ip(request), description=user.get_username())


def _logged_out(sender, request, user, **kwargs):
    if user is not None:
        log_event(Action.LOGOUT, user=user, ip=request_ip(request), description=user.get_username())


def _login_failed(sender, credentials, request=None, **kwargs):
    # Only the username is kept; the password typed is never stored.
    name = str(credentials.get("username", ""))[:150]
    log_event(
        Action.LOGIN_FAILED,
        ip=request_ip(request) if request is not None else None,
        description=f"usuário informado: {name}",
    )


user_logged_in.connect(_logged_in, dispatch_uid="auditoria_login")
user_logged_out.connect(_logged_out, dispatch_uid="auditoria_logout")
user_login_failed.connect(_login_failed, dispatch_uid="auditoria_login_falhou")
