from django.conf import settings
from django.db import models


class RegistroAuditoria(models.Model):
    """Who did what, when and from where (LGPD accountability). Never edited or deleted,
    except failed logins, deleted after 30 days by the aplicar_retencao command, and the
    personal data of a patient deleted at their request (registro.anonimizar).

    Not a ModeloDaClinica: entries must be written in every context (including
    platform code running with sem_isolamento), and some have no clinic (logins).
    Views always filter by clinic explicitly.
    """

    class Acao(models.TextChoices):
        CRIAR = "criar", "Criou"
        ALTERAR = "alterar", "Alterou"
        EXCLUIR = "excluir", "Excluiu"
        VISUALIZAR = "visualizar", "Visualizou"
        LOGIN = "login", "Entrou no sistema"
        LOGIN_FALHOU = "login_falhou", "Tentativa de entrada recusada"
        LOGOUT = "logout", "Saiu do sistema"

    momento = models.DateTimeField("quando", auto_now_add=True, db_index=True)
    # No database constraint: history keeps the ids even after a clinic or user is
    # deleted, and writing an entry never blocks a deletion.
    clinica = models.ForeignKey(
        "core.Clinica",
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="clínica",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING,
        db_constraint=False,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="usuário",
    )
    # Kept as text so the entry still says who it was if the user is deleted.
    usuario_nome = models.CharField("usuário (texto)", max_length=150, blank=True)
    acao = models.CharField("ação", max_length=20, choices=Acao.choices)
    modelo = models.CharField("tipo de registro", max_length=50, blank=True)
    objeto_id = models.CharField("código do registro", max_length=40, blank=True)
    objeto_descricao = models.CharField("registro", max_length=200, blank=True)
    alteracoes = models.JSONField("alterações", default=dict, blank=True)
    ip = models.GenericIPAddressField("IP", null=True, blank=True)

    class Meta:
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"
        ordering = ["-momento", "-pk"]
        indexes = [
            models.Index(fields=["clinica", "-momento"], name="auditoria_clinica_momento"),
            models.Index(fields=["modelo", "objeto_id"], name="auditoria_objeto"),
        ]

    def __str__(self):
        quem = self.usuario_nome or "sistema"
        acao = self.get_acao_display()
        return f"{self.momento:%d/%m/%Y %H:%M} {quem}: {acao} {self.objeto_descricao}"
