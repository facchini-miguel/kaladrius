from apps.core import modulos
from apps.core.models import ModuloClinico, Papel
from apps.profissionais.models import Profissional


def prontuario_habilitado(request):
    """The clinic has the medical record module on (decision 092)."""
    return ModuloClinico.PRONTUARIO in modulos.habilitados(request)


def administra_prontuario(request):
    """The system administrator (superuser) sees and does everything in the medical record,
    writing on behalf of a practitioner (decision 087). Clinic administrators do not."""
    return (
        request.user.is_authenticated
        and request.user.is_superuser
        and prontuario_habilitado(request)
    )


def acessa_prontuario(request):
    return administra_prontuario(request) or (
        prontuario_habilitado(request) and profissional_do_usuario(request) is not None
    )


def profissional_do_usuario(request):
    """The practitioner record of the logged-in user, or None (decision 081).

    Practitioners read and write the medical record: never the front desk, and a clinic
    administrator only when also registered as an active practitioner (Cadastros >
    Profissionais, linked to their user). The superuser always reaches it (decision 087).
    """
    if not hasattr(request, "_profissional_do_prontuario"):
        request._profissional_do_prontuario = _profissional(request)
    return request._profissional_do_prontuario


def _profissional(request):
    usuario = request.user
    if not usuario.is_authenticated or getattr(request, "clinica", None) is None:
        return None
    vinculo = getattr(request, "vinculo", None)
    if vinculo is None and not usuario.is_superuser:
        return None
    if vinculo is not None and vinculo.papel == Papel.RECEPCAO:
        return None
    return Profissional.objects.filter(usuario=usuario, ativo=True).first()
