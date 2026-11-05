from apps.core import modules
from apps.core.models import ModuleCode, Role
from apps.practitioners.models import Practitioner


def prontuario_habilitado(request):
    """The clinic has the medical record module on (decision 092)."""
    return ModuleCode.MEDICAL_RECORDS in modules.enabled(request)


def administra_prontuario(request):
    """The system administrator (superuser) sees and does everything in the medical record,
    writing on behalf of a practitioner (decision 087), even with the module turned off
    (decision 115). Clinic administrators do not."""
    return (
        request.user.is_authenticated
        and request.user.is_superuser
        and ModuleCode.MEDICAL_RECORDS in modules.visible(request)
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
    user = request.user
    if not user.is_authenticated or getattr(request, "clinic", None) is None:
        return None
    vinculo = getattr(request, "vinculo", None)
    if vinculo is None and not user.is_superuser:
        return None
    if vinculo is not None and vinculo.role == Role.FRONT_DESK:
        return None
    return Practitioner.objects.filter(user=user, active=True).first()
