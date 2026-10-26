from django.urls import reverse

from .isolamento import sem_isolamento, usar_clinica
from .models import Clinica, Vinculo

SESSAO_CLINICA = "clinica_id"


def clinicas_do_usuario(usuario):
    """Active clinics the user may work in. Superusers may work in any clinic."""
    if usuario.is_superuser:
        return Clinica.objects.filter(ativa=True)
    return Clinica.objects.filter(
        ativa=True, vinculos__usuario=usuario, vinculos__ativo=True
    ).distinct()


def resolver_clinica(request):
    """Return (clinic, membership) for the request, validating the session choice.

    The clinic stored in the session is only honored if the user still has an
    active membership in it (or is a superuser). Otherwise the first available
    clinic is used. Returns (None, None) when the user has no clinic at all.
    """
    usuario = request.user
    vinculos = list(
        Vinculo.objects.filter(usuario=usuario, ativo=True, clinica__ativa=True)
        .select_related("clinica")
        .order_by("clinica__nome")
    )
    escolhida = request.session.get(SESSAO_CLINICA)
    if escolhida is not None:
        for vinculo in vinculos:
            if vinculo.clinica_id == escolhida:
                return vinculo.clinica, vinculo
        if usuario.is_superuser:
            clinica = Clinica.objects.filter(pk=escolhida, ativa=True).first()
            if clinica is not None:
                return clinica, None
        del request.session[SESSAO_CLINICA]
    if vinculos:
        request.session[SESSAO_CLINICA] = vinculos[0].clinica_id
        return vinculos[0].clinica, vinculos[0]
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
