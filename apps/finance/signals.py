from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Clinic

from .models import create_defaults


@receiver(post_save, sender=Clinic, dispatch_uid="financeiro_padroes")
def defaults_for_new_clinic(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        create_defaults(instance)
