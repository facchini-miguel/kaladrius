from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Clinica
from .modulos import configurar, iniciais


@receiver(post_save, sender=Clinica, dispatch_uid="core_modulos_iniciais")
def modulos_para_clinica_nova(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        configurar(instance, iniciais(instance.area))
