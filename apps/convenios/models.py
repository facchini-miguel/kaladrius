"""Health plans the clinic accepts and the patients' cards (decision 094).

Taken from the legacy Medical system (medical_convenios, medical_convenios_pessoas). This
first step is the register only: authorizations and billing the plan are another scope.
"""

from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.isolamento import ClinicaDiferente, ModeloDaClinica


class Convenio(ModeloDaClinica):
    nome = models.CharField(_("nome"), max_length=200)
    registro_ans = models.CharField(
        _("registro na ANS"),
        max_length=6,
        blank=True,
        help_text=_("Os 6 dígitos do registro da operadora na ANS, se houver."),
    )
    telefone = models.CharField(_("telefone"), max_length=11, blank=True)
    observacoes = models.TextField(_("observações"), blank=True)
    ativo = models.BooleanField(_("ativo"), default=True)
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)
    alterado_em = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        verbose_name = _("convênio")
        verbose_name_plural = _("convênios")
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                "clinica", Lower("nome"), name="convenio_nome_unico_por_clinica"
            ),
        ]

    def __str__(self):
        return self.nome


class Carteirinha(ModeloDaClinica):
    """A patient's card of a health plan."""

    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.PROTECT,
        related_name="carteirinhas",
        verbose_name=_("paciente"),
    )
    convenio = models.ForeignKey(
        Convenio, on_delete=models.PROTECT, related_name="carteirinhas", verbose_name=_("convênio")
    )
    plano = models.CharField(_("plano"), max_length=100, blank=True)
    numero = models.CharField(_("número da carteirinha"), max_length=30)
    validade = models.DateField(_("validade"), null=True, blank=True)
    titular = models.CharField(
        _("titular"),
        max_length=200,
        blank=True,
        help_text=_("Se o paciente for dependente, o nome do titular do plano."),
    )
    ativa = models.BooleanField(_("ativa"), default=True)
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)
    alterado_em = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        verbose_name = _("carteirinha")
        verbose_name_plural = _("carteirinhas")
        ordering = ["-ativa", "convenio__nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["clinica", "convenio", "numero"], name="carteirinha_unica_por_convenio"
            ),
        ]

    def __str__(self):
        return f"{self.convenio} {self.numero}"

    def save(self, *args, **kwargs):
        # Having clinica_id on every row does not stop a link across clinics on its own.
        self._conferir_clinica()
        if self.clinica_id is None:  # without isolation (commands)
            self.clinica_id = self.paciente.clinica_id
        if {self.paciente.clinica_id, self.convenio.clinica_id} != {self.clinica_id}:
            raise ClinicaDiferente("The patient and the health plan must be of this clinic.")
        super().save(*args, **kwargs)

    @property
    def vencida(self):
        return self.validade is not None and self.validade < timezone.localdate()
