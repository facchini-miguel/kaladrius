from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditEntry(models.Model):
    """Who did what, when and from where (LGPD accountability). Never edited or deleted,
    except failed logins, deleted after 30 days by the apply_retention command, and the
    personal data of a patient deleted at their request (registro.anonimizar).

    Not a ModeloDaClinica: entries must be written in every context (including
    platform code running with sem_isolamento), and some have no clinic (logins).
    Views always filter by clinic explicitly.
    """

    class Action(models.TextChoices):
        CREATE = "create", _("Created")
        CHANGE = "change", _("Changed")
        DELETE = "delete", _("Deleted")
        VIEWED = "viewed", _("Viewed")
        LOGIN = "login", _("Logged in")
        LOGIN_FAILED = "login_failed", _("Login attempt refused")
        LOGOUT = "logout", _("Logged out")

    timestamp = models.DateTimeField(_("when"), auto_now_add=True, db_index=True)
    # No database constraint: history keeps the ids even after a clinic or user is
    # deleted, and writing an entry never blocks a deletion.
    clinic = models.ForeignKey(
        "core.Clinic",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("clinic"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("user"),
    )
    # Kept as text so the entry still says who it was if the user is deleted.
    user_name = models.CharField(_("user (text)"), max_length=150, blank=True)
    action = models.CharField(_("action"), max_length=20, choices=Action.choices)
    model_name = models.CharField(_("record type"), max_length=50, blank=True)
    object_id = models.CharField(_("record code"), max_length=40, blank=True)
    object_repr = models.CharField(_("record"), max_length=200, blank=True)
    changes = models.JSONField(_("changes"), default=dict, blank=True)
    ip = models.GenericIPAddressField(_("IP"), null=True, blank=True)

    class Meta:
        db_table = "audit_entry"
        verbose_name = _("audit entry")
        verbose_name_plural = _("audit entries")
        ordering = ["-timestamp", "-pk"]
        indexes = [
            models.Index(fields=["clinic", "-timestamp"], name="audit_clinic_timestamp"),
            models.Index(fields=["model_name", "object_id"], name="audit_object"),
        ]

    def __str__(self):
        who = self.user_name or "sistema"
        action = self.get_action_display()
        return f"{self.timestamp:%d/%m/%Y %H:%M} {who}: {action} {self.object_repr}"
