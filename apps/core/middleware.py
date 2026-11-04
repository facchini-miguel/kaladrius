import zoneinfo

from django.urls import reverse
from django.utils import timezone, translation

from . import countries
from .isolation import sem_isolamento, usar_clinica
from .models import Clinic, Membership


def resolver_clinica(request):
    """Return (clinic, membership) for the request.

    One installation serves one clinic (decision 069), so nobody chooses: a user works in
    the clinic of their active membership, and a superuser without one in the clinic of
    the installation. Returns (None, None) when there is no clinic for the user.
    """
    user = request.user
    vinculo = (
        Membership.objects.filter(user=user, active=True, clinic__active=True)
        .select_related("clinic")
        .order_by("clinic_id")
        .first()
    )
    if vinculo is not None:
        return vinculo.clinic, vinculo
    if user.is_superuser:
        return Clinic.unica(), None
    return None, None


class ClinicaAtualMiddleware:
    """Sets request.clinica / request.vinculo and the isolation context for the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.clinic = None
        request.vinculo = None
        if request.path_info.startswith(reverse("admin:index")):
            # The Django admin is restricted to platform superusers (see core/admin.py)
            # and works across every clinic.
            with sem_isolamento():
                return self.get_response(request)
        if request.user.is_authenticated:
            request.clinic, request.vinculo = resolver_clinica(request)
        if request.clinic is not None:
            _usar_pais_da_clinica(request, request.clinic)
        try:
            with usar_clinica(request.clinic):
                return self.get_response(request)
        finally:
            timezone.deactivate()


def _usar_pais_da_clinica(request, clinic):
    """The clinic's time zone, and the English variant of its country for dates and times
    (decision 117): an English-speaking user of a British clinic gets 31/10/2026."""
    try:
        timezone.activate(zoneinfo.ZoneInfo(clinic.fuso_horario))
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        pass  # an unknown zone keeps settings.TIME_ZONE
    variante = countries.variante_do_idioma(translation.get_language(), clinic.pais)
    if variante:
        translation.activate(variante)
        request.LANGUAGE_CODE = variante


class ProxyReversoMiddleware:
    """Use the client IP reported by the reverse proxy (Caddy) as REMOTE_ADDR.

    Only enabled with DJANGO_REVERSE_PROXY=1, where the app port is reachable solely
    by the proxy; otherwise anyone could forge the header. The proxy sets the client
    address as the last X-Forwarded-For entry.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        encaminhado = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if encaminhado:
            request.META["REMOTE_ADDR"] = encaminhado.split(",")[-1].strip()
        return self.get_response(request)


class IdiomaDoUsuarioMiddleware:
    """Activate the language chosen by the logged-in user (after LocaleMiddleware)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        idioma = getattr(getattr(request, "user", None), "idioma", "")
        if idioma:
            translation.activate(idioma)
            request.LANGUAGE_CODE = idioma
        return self.get_response(request)
