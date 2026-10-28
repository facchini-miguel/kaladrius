from django.urls import reverse
from django.utils import translation

from .isolamento import sem_isolamento, usar_clinica
from .models import Clinica, Vinculo


def resolver_clinica(request):
    """Return (clinic, membership) for the request.

    One installation serves one clinic (decision 069), so nobody chooses: a user works in
    the clinic of their active membership, and a superuser without one in the clinic of
    the installation. Returns (None, None) when there is no clinic for the user.
    """
    usuario = request.user
    vinculo = (
        Vinculo.objects.filter(usuario=usuario, ativo=True, clinica__ativa=True)
        .select_related("clinica")
        .order_by("clinica_id")
        .first()
    )
    if vinculo is not None:
        return vinculo.clinica, vinculo
    if usuario.is_superuser:
        return Clinica.unica(), None
    return None, None


class ClinicaAtualMiddleware:
    """Sets request.clinica / request.vinculo and the isolation context for the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.clinica = None
        request.vinculo = None
        if request.path_info.startswith(reverse("admin:index")):
            # The Django admin is restricted to platform superusers (see core/admin.py)
            # and works across every clinic.
            with sem_isolamento():
                return self.get_response(request)
        if request.user.is_authenticated:
            request.clinica, request.vinculo = resolver_clinica(request)
        with usar_clinica(request.clinica):
            return self.get_response(request)


class ProxyReversoMiddleware:
    """Use the client IP reported by the reverse proxy (Caddy) as REMOTE_ADDR.

    Only enabled with DJANGO_PROXY_REVERSO=1, where the app port is reachable solely
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
