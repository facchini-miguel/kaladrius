from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Clinic
from .modules import configure, initial


@receiver(post_save, sender=Clinic, dispatch_uid="core_initial_modules")
def modules_for_new_clinic(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        configure(instance, initial(instance.area))
