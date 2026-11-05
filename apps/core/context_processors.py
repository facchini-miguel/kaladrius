import datetime

from django.conf import settings
from django.utils import timezone, translation
from django.utils.functional import SimpleLazyObject

from . import countries, identification, modules
from .models import Backup
from .permissions import permissions_table

# A daily backup runs at 06:00 UTC; older than this means at least one was missed.
BACKUP_LATE_AFTER = datetime.timedelta(hours=26)


def clinic(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {
        "clinica_atual": getattr(request, "clinic", None),
        "vinculo_atual": getattr(request, "vinculo", None),
        "pode": SimpleLazyObject(lambda: permissions_table(request)),
        # Turned-off modules the system administrator still sees (decision 115): marked in
        # the menu, and the page of one says so.
        "modulos_desligados": SimpleLazyObject(lambda: modules.visible_disabled(request)),
        "modulo_desligado": getattr(request, "modulo_desligado", None),
        # Brazilian fields (RG, state registration, IBGE cities) are shown only in Brazil
        # (decision 117); the documents are the country's (decision 121).
        "no_brasil": countries.clinic_country(getattr(request, "clinic", None)) == "BR",
        "documentos_do_pais": identification.for_country(
            countries.clinic_country(getattr(request, "clinic", None))
        ),
    }


def languages(request):
    """Languages for the top bar menu, each one named in itself ("English", "Español"):
    get_available_languages would translate the names into the current language."""
    current = translation.get_language()
    # A country's English (en-gb, en-au... decision 117) is still "English" in the menu.
    base = next(
        (code for code, _nome in settings.LANGUAGES if current.split("-")[0] == code), current
    )
    return {
        "idiomas": settings.LANGUAGES,
        "idioma_base": base,
        "idioma_nome": dict(settings.LANGUAGES).get(base, current),
    }


def backup(request):
    """For superusers on servers with backups: a warning when the newest one is overdue
    or when no backup was ever recorded (backups never worked)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_superuser or not settings.BACKUP_MONITORED:
        return {}
    last = Backup.objects.first()
    if last is None:
        return {"backup_nenhum": True}
    if timezone.now() - last.timestamp <= BACKUP_LATE_AFTER:
        return {}
    return {"backup_atrasado": last}


def inactivity(request):
    """Minutes without use before the page leaves by itself (decision 111)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"inatividade_minutos": settings.IDLE_MINUTES}
