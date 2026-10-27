from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Clinica

from .models import criar_padroes


@receiver(post_save, sender=Clinica, dispatch_uid="financeiro_padroes")
def padroes_para_clinica_nova(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        criar_padroes(instance)
