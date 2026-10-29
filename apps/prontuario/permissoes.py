from apps.core.models import Papel
from apps.profissionais.models import Profissional


def profissional_do_usuario(request):
    """The practitioner record of the logged-in user, or None (decision 081).

    Only practitioners read and write the medical record: never the front desk, and an
    administrator or the superuser only when also registered as an active practitioner
    (Cadastros > Profissionais, linked to their user).
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
