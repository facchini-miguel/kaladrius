import datetime

from django.conf import settings
from django.utils import timezone, translation
from django.utils.functional import SimpleLazyObject

from .middleware import clinicas_do_usuario
from .models import Backup
from .permissoes import tabela_permissoes

# A daily backup runs at 06:00 UTC; older than this means at least one was missed.
BACKUP_ATRASADO_APOS = datetime.timedelta(hours=26)


def clinica(request):
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    return {
        "clinica_atual": getattr(request, "clinica", None),
        "vinculo_atual": getattr(request, "vinculo", None),
        "pode": SimpleLazyObject(lambda: tabela_permissoes(request)),
        "clinicas_do_usuario": SimpleLazyObject(lambda: list(clinicas_do_usuario(usuario))),
    }


def idiomas(request):
    """Languages for the top bar menu, each one named in itself ("English", "Español"):
    get_available_languages would translate the names into the current language."""
    atual = translation.get_language()
    return {
        "idiomas": settings.LANGUAGES,
        "idioma_nome": dict(settings.LANGUAGES).get(atual, atual),
    }


def backup(request):
    """For superusers: the newest backup, when it is overdue (backups stopped working).

    Environments that never recorded a backup (development) show nothing.
    """
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_superuser:
        return {}
    ultimo = Backup.objects.first()
    if ultimo is None or timezone.now() - ultimo.momento <= BACKUP_ATRASADO_APOS:
        return {}
    return {"backup_atrasado": ultimo}
