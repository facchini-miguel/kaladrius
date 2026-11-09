import zoneinfo

from django.urls import reverse
from django.utils import timezone, translation

from . import countries
from .isolation import use_clinic, without_isolation
from .models import Clinic, Membership


def resolve_clinic(request):
    """Return (clinic, membership) for the request.

    One installation serves one clinic (decision 069), so nobody chooses: a user works in
    the clinic of their active membership, and a superuser without one in the clinic of
    the installation. Returns (None, None) when there is no clinic for the user.
    """
    user = request.user
    membership = (
        Membership.objects.filter(user=user, active=True, clinic__active=True)
        .select_related("clinic")
        .order_by("clinic_id")
        .first()
    )
    if membership is not None:
        return membership.clinic, membership
    if user.is_superuser:
        return Clinic.single(), None
    return None, None


class CurrentClinicMiddleware:
    """Sets request.clinica / request.vinculo and the isolation context for the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.clinic = None
        request.membership = None
        if request.path_info.startswith(reverse("admin:index")):
            # The Django admin is restricted to platform superusers (see core/admin.py)
            # and works across every clinic.
            with without_isolation():
                return self.get_response(request)
        if request.user.is_authenticated:
            request.clinic, request.membership = resolve_clinic(request)
        if request.clinic is not None:
            _use_clinic_country(request, request.clinic)
        try:
            with use_clinic(request.clinic):
                return self.get_response(request)
        finally:
            timezone.deactivate()


def _use_clinic_country(request, clinic):
    """The clinic's time zone, and the English variant of its country for dates and times
    (decision 117): an English-speaking user of a British clinic gets 31/10/2026."""
    try:
        timezone.activate(zoneinfo.ZoneInfo(clinic.time_zone))
    except (zoneinfo.ZoneInfoNotFoundError, ValueError):
        pass  # an unknown zone keeps settings.TIME_ZONE
    variant = countries.language_variant(translation.get_language(), clinic.country)
    if variant:
        translation.activate(variant)
        request.LANGUAGE_CODE = variant


class ReverseProxyMiddleware:
    """Use the client IP reported by the reverse proxy (Caddy) as REMOTE_ADDR.

    Only enabled with DJANGO_REVERSE_PROXY=1, where the app port is reachable solely
    by the proxy; otherwise anyone could forge the header. The proxy sets the client
    address as the last X-Forwarded-For entry.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            request.META["REMOTE_ADDR"] = forwarded.split(",")[-1].strip()
        return self.get_response(request)


class UserLanguageMiddleware:
    """Activate the language chosen by the logged-in user (after LocaleMiddleware)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = getattr(getattr(request, "user", None), "language", "")
        if language:
            translation.activate(language)
            request.LANGUAGE_CODE = language
        return self.get_response(request)


class NoIndexMiddleware:
    """Asks search engines not to list any page of the system (decision 207).

    An installation is a clinic's private system: its address must never turn up in a
    search. The public pages about the project are the website and the documentation,
    which are indexed. A header rather than a robots.txt block, so engines that already
    know an address (from a link) read it and drop it.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response
