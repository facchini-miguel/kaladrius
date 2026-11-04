import datetime

from django.conf import settings
from django.utils import timezone, translation
from django.utils.functional import SimpleLazyObject

from . import countries, identification, modules
from .models import Backup
from .permissions import tabela_permissoes

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
        # Turned-off modules the system administrator still sees (decision 115): marked in
        # the menu, and the page of one says so.
        "modulos_desligados": SimpleLazyObject(lambda: modules.desligados_visiveis(request)),
        "modulo_desligado": getattr(request, "modulo_desligado", None),
        # Brazilian fields (RG, state registration, IBGE cities) are shown only in Brazil
        # (decision 117); the documents are the country's (decision 121).
        "no_brasil": countries.pais_da_clinica(getattr(request, "clinica", None)) == "BR",
        "documentos_do_pais": identification.do_pais(
            countries.pais_da_clinica(getattr(request, "clinica", None))
        ),
    }


def idiomas(request):
    """Languages for the top bar menu, each one named in itself ("English", "Español"):
    get_available_languages would translate the names into the current language."""
    atual = translation.get_language()
    # A country's English (en-gb, en-au... decision 117) is still "English" in the menu.
    base = next(
        (codigo for codigo, _nome in settings.LANGUAGES if atual.split("-")[0] == codigo), atual
    )
    return {
        "idiomas": settings.LANGUAGES,
        "idioma_base": base,
        "idioma_nome": dict(settings.LANGUAGES).get(base, atual),
    }


def backup(request):
    """For superusers on servers with backups: a warning when the newest one is overdue
    or when no backup was ever recorded (backups never worked)."""
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_superuser or not settings.BACKUP_MONITORED:
        return {}
    ultimo = Backup.objects.first()
    if ultimo is None:
        return {"backup_nenhum": True}
    if timezone.now() - ultimo.momento <= BACKUP_ATRASADO_APOS:
        return {}
    return {"backup_atrasado": ultimo}


def inatividade(request):
    """Minutes without use before the page leaves by itself (decision 111)."""
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_authenticated:
        return {}
    return {"inatividade_minutos": settings.INATIVIDADE_MINUTOS}
