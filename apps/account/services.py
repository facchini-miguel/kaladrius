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

from apps.core.security import ip_para_bloqueio

from .models import RecoveryCode, TwoFactor

# Wrong logins from one address in the cooling-off time, whatever the username: stops someone
# from trying a common password on many users (the per-user lock only counts 5 per user).
LIMITE_POR_ENDERECO = 20
QUANTOS_CODIGOS = 10
ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I to confuse


def tentativas_do_endereco(request):
    desde = timezone.now() - datetime.timedelta(hours=settings.AXES_COOLOFF_TIME)
    total = AccessAttempt.objects.filter(
        ip_address=ip_para_bloqueio(request), attempt_time__gte=desde
    ).aggregate(total=Sum("failures_since_start"))["total"]
    return total or 0


def endereco_bloqueado(request):
    return tentativas_do_endereco(request) >= LIMITE_POR_ENDERECO


def ativa_para(user):
    return TwoFactor.objects.filter(user=user, active=True).exists()


def obrigatoria(request):
    """Whether the clinic requires two-step verification from this person (decision 112):
    whoever reaches the medical record or the full finance, never the public demo logins."""
    from apps.core.permissions import Acao, Modulo, pode
    from apps.medical_records.permissions import acessa_prontuario

    user, clinic = request.user, getattr(request, "clinic", None)
    if not user.is_authenticated or user.demonstracao or clinic is None:
        return False
    if not clinic.exigir_duas_etapas:
        return False
    return pode(request, Modulo.FINANCEIRO, Acao.VER) or acessa_prontuario(request)


def preparar(user, novo=False):
    """The person's not yet active device, with a secret to show as a QR code."""
    dispositivo, criado = TwoFactor.objects.get_or_create(
        user=user, defaults={"segredo": pyotp.random_base32()}
    )
    if novo and not criado and not dispositivo.active:
        dispositivo.segredo = pyotp.random_base32()
        dispositivo.save(update_fields=["segredo"])
    return dispositivo


def endereco_do_app(dispositivo):
    """The otpauth:// address the authenticator app reads from the QR code."""
    return pyotp.TOTP(dispositivo.segredo).provisioning_uri(
        name=dispositivo.user.get_username(), issuer_name=settings.NOME_SISTEMA
    )


def qr_svg(endereco):
    return segno.make(endereco, error="m").svg_inline(scale=5, dark="#212529", border=2)


def segredo_em_grupos(segredo):
    return " ".join(segredo[i : i + 4] for i in range(0, len(segredo), 4))


def verificar_app(dispositivo, code):
    """A 6-digit code from the app, accepting the step before and after (clock drift)."""
    code = re.sub(r"\D", "", code or "")
    if len(code) != 6:
        return False
    totp = pyotp.TOTP(dispositivo.segredo)
    agora = int(timezone.now().timestamp() // totp.interval)
    for passo in (agora - 1, agora, agora + 1):
        if passo > dispositivo.ultimo_passo and hmac.compare_digest(
            totp.at(passo * totp.interval), code
        ):
            dispositivo.ultimo_passo = passo
            dispositivo.save(update_fields=["ultimo_passo"])
            return True
    return False


def _resumo(code):
    limpo = re.sub(r"[^A-Z0-9]", "", (code or "").upper())
    return hmac.new(settings.SECRET_KEY.encode(), limpo.encode(), hashlib.sha256).hexdigest()


@transaction.atomic
def novos_codigos(user):
    """Ten new recovery codes (the old ones stop working), shown once."""
    RecoveryCode.objects.filter(user=user).delete()
    codigos = [
        "-".join("".join(secrets.choice(ALFABETO) for _ in range(4)) for _ in range(2))
        for _ in range(QUANTOS_CODIGOS)
    ]
    RecoveryCode.objects.bulk_create(RecoveryCode(user=user, resumo=_resumo(c)) for c in codigos)
    return codigos


def verificar_recuperacao(user, code):
    restante = RecoveryCode.objects.filter(
        user=user, resumo=_resumo(code), usado_em__isnull=True
    ).first()
    if restante is None:
        return False
    restante.usado_em = timezone.now()
    restante.save(update_fields=["usado_em"])
    return True


def verificar(user, code):
    """The app's code or an unused recovery code."""
    dispositivo = TwoFactor.objects.filter(user=user, active=True).first()
    if dispositivo is None:
        return False
    return verificar_app(dispositivo, code) or verificar_recuperacao(user, code)


@transaction.atomic
def ativar(dispositivo):
    dispositivo.active = True
    dispositivo.ativada_em = timezone.now()
    dispositivo.save(update_fields=["active", "ativada_em"])
    return novos_codigos(dispositivo.user)


@transaction.atomic
def desativar(user):
    TwoFactor.objects.filter(user=user).delete()
    RecoveryCode.objects.filter(user=user).delete()
