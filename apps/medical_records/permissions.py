from apps.core import modules
from apps.core.models import ModuleCode, Role
from apps.practitioners.models import Practitioner


def medical_records_enabled(request):
    """The clinic has the medical record module on (decision 092)."""
    return ModuleCode.MEDICAL_RECORDS in modules.enabled(request)


def manages_medical_records(request):
    """The system administrator (superuser) sees and does everything in the medical record,
    writing on behalf of a practitioner (decision 087), even with the module turned off
    (decision 115). Clinic administrators do not."""
    return (
        request.user.is_authenticated
        and request.user.is_superuser
        and ModuleCode.MEDICAL_RECORDS in modules.visible(request)
    )


def accesses_medical_records(request):
    return manages_medical_records(request) or (
        medical_records_enabled(request) and user_practitioner(request) is not None
    )


def user_practitioner(request):
    """The practitioner record of the logged-in user, or None (decision 081).

    Practitioners read and write the medical record: never the front desk, and a clinic
    administrator only when also registered as an active practitioner (Cadastros >
    Profissionais, linked to their user). The superuser always reaches it (decision 087).
    """
    if not hasattr(request, "_profissional_do_prontuario"):
        request._profissional_do_prontuario = _practitioner(request)
    return request._profissional_do_prontuario


def _practitioner(request):
    user = request.user
    if not user.is_authenticated or getattr(request, "clinic", None) is None:
        return None
    vinculo = getattr(request, "vinculo", None)
    if vinculo is None and not user.is_superuser:
        return None
    if vinculo is not None and vinculo.role == Role.FRONT_DESK:
        return None
    return Practitioner.objects.filter(user=user, active=True).first()
