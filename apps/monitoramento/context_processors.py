from django.conf import settings

from . import saude


def alerta(request):
    """For superusers on monitored servers: a warning when the health samples stop or
    memory, swap or disk reach the critical level."""
    usuario = getattr(request, "user", None)
    if usuario is None or not usuario.is_superuser or not settings.SAUDE_MONITORADA:
        return {}
    ultima = saude.ultima()
    if ultima is None:
        return {"saude_alerta": {"sem_coleta": True}}
    if saude.parada(ultima):
        return {"saude_alerta": {"parada": ultima["momento"]}}
    # Not the processor: a busy moment is normal, and it does not break anything by itself.
    criticos = [
        chave
        for chave, nivel in saude.niveis(ultima).items()
        if nivel == "critico" and chave != "cpu"
    ]
    return {"saude_alerta": {"criticos": criticos}} if criticos else {}
