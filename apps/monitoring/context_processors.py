from django.conf import settings

from . import health


def alerta(request):
    """For superusers on monitored servers: a warning when the health samples stop or
    memory, swap or disk reach the critical level."""
    user = getattr(request, "user", None)
    if user is None or not user.is_superuser or not settings.HEALTH_MONITORED:
        return {}
    ultima = health.ultima()
    if ultima is None:
        return {"saude_alerta": {"sem_coleta": True}}
    if health.parada(ultima):
        return {"saude_alerta": {"parada": ultima["momento"]}}
    # Not the processor: a busy moment is normal, and it does not break anything by itself.
    criticos = [
        chave
        for chave, nivel in health.niveis(ultima).items()
        if nivel == "critico" and chave != "cpu"
    ]
    return {"saude_alerta": {"criticos": criticos}} if criticos else {}
