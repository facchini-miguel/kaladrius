from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    """System user.

    Custom model from day one so new fields (e.g., clinic memberships in step 2)
    can be added later without painful migrations.
    """

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
