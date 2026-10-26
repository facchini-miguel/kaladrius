from django.contrib.auth.models import AbstractUser


class Usuario(AbstractUser):
    """Usuário do sistema.

    Modelo próprio desde o início para permitir novos campos (ex.: vínculo com
    clínicas na etapa 2) sem migrações difíceis depois.
    """

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
