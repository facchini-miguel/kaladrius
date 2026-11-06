"""Login protections (decision 111): attempts per address, authenticator codes and recovery
codes for two-step verification."""

import datetime
import hashlib
import hmac
import re
import secrets

import pyotp
import segno
from axes.models import AccessAttempt
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.security import ip_for_lockout

from .models import RecoveryCode, TwoFactor

# Wrong logins from one address in the cooling-off time, whatever the username: stops someone
# from trying a common password on many users (the per-user lock only counts 5 per user).
LIMIT_PER_ADDRESS = 20
CODE_COUNT = 10
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I to confuse


def address_attempts(request):
    desde = timezone.now() - datetime.timedelta(hours=settings.AXES_COOLOFF_TIME)
    total = AccessAttempt.objects.filter(
        ip_address=ip_for_lockout(request), attempt_time__gte=desde
    ).aggregate(total=Sum("failures_since_start"))["total"]
    return total or 0


def address_blocked(request):
    return address_attempts(request) >= LIMIT_PER_ADDRESS


def active_for(user):
    return TwoFactor.objects.filter(user=user, active=True).exists()


def is_required(request):
    """Whether the clinic requires two-step verification from this person (decision 112):
    whoever reaches the medical record or the full finance, never the public demo logins."""
    from apps.core.permissions import Action, Module, can
    from apps.medical_records.permissions import accesses_medical_records

    user, clinic = request.user, getattr(request, "clinic", None)
    if not user.is_authenticated or user.demo or clinic is None:
        return False
    if not clinic.require_two_factor:
        return False
    return can(request, Module.FINANCE, Action.VIEW) or accesses_medical_records(request)


def prepare(user, new=False):
    """The person's not yet active device, with a secret to show as a QR code."""
    dispositivo, criado = TwoFactor.objects.get_or_create(
        user=user, defaults={"secret": pyotp.random_base32()}
    )
    if new and not criado and not dispositivo.active:
        dispositivo.secret = pyotp.random_base32()
        dispositivo.save(update_fields=["secret"])
    return dispositivo


def app_uri(dispositivo):
    """The otpauth:// address the authenticator app reads from the QR code."""
    return pyotp.TOTP(dispositivo.secret).provisioning_uri(
        name=dispositivo.user.get_username(), issuer_name=settings.SYSTEM_NAME
    )


def qr_svg(address):
    return segno.make(address, error="m").svg_inline(scale=5, dark="#212529", border=2)


def secret_in_groups(secret):
    return " ".join(secret[i : i + 4] for i in range(0, len(secret), 4))


def verify_app(dispositivo, code):
    """A 6-digit code from the app, accepting the step before and after (clock drift)."""
    code = re.sub(r"\D", "", code or "")
    if len(code) != 6:
        return False
    totp = pyotp.TOTP(dispositivo.secret)
    now = int(timezone.now().timestamp() // totp.interval)
    for passo in (now - 1, now, now + 1):
        if passo > dispositivo.last_step and hmac.compare_digest(
            totp.at(passo * totp.interval), code
        ):
            dispositivo.last_step = passo
            dispositivo.save(update_fields=["last_step"])
            return True
    return False


def _digest(code):
    limpo = re.sub(r"[^A-Z0-9]", "", (code or "").upper())
    return hmac.new(settings.SECRET_KEY.encode(), limpo.encode(), hashlib.sha256).hexdigest()


@transaction.atomic
def new_codes(user):
    """Ten new recovery codes (the old ones stop working), shown once."""
    RecoveryCode.objects.filter(user=user).delete()
    codigos = [
        "-".join("".join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(2))
        for _ in range(CODE_COUNT)
    ]
    RecoveryCode.objects.bulk_create(RecoveryCode(user=user, digest=_digest(c)) for c in codigos)
    return codigos


def verify_recovery(user, code):
    restante = RecoveryCode.objects.filter(
        user=user, digest=_digest(code), used_at__isnull=True
    ).first()
    if restante is None:
        return False
    restante.used_at = timezone.now()
    restante.save(update_fields=["used_at"])
    return True


def verify(user, code):
    """The app's code or an unused recovery code."""
    dispositivo = TwoFactor.objects.filter(user=user, active=True).first()
    if dispositivo is None:
        return False
    return verify_app(dispositivo, code) or verify_recovery(user, code)


@transaction.atomic
def activate(dispositivo):
    dispositivo.active = True
    dispositivo.activated_at = timezone.now()
    dispositivo.save(update_fields=["active", "activated_at"])
    return new_codes(dispositivo.user)


@transaction.atomic
def deactivate(user):
    TwoFactor.objects.filter(user=user).delete()
    RecoveryCode.objects.filter(user=user).delete()
