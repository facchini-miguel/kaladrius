"""Procedure price list and treatment estimates (0.18.0).

An estimate (Orcamento) lists procedures for a patient, optionally per tooth (FDI
numbering, picked on a clickable dental chart). When the patient approves it, it becomes a
receivable (financeiro.Lancamento) in the chosen installments.
"""

import datetime
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.isolamento import ModeloDaClinica

DINHEIRO = {"max_digits": 12, "decimal_places": 2}
VALIDADE_PADRAO = 30  # days


def validade_padrao():
    return timezone.localdate() + datetime.timedelta(days=VALIDADE_PADRAO)


class Procedimento(ModeloDaClinica):
    """An item of the clinic's price list (cleaning, filling, root canal...)."""

    nome = models.CharField(_("nome"), max_length=120)
    valor = models.DecimalField(_("valor"), **DINHEIRO)
    categoria = models.ForeignKey(
        "financeiro.Categoria",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("categoria"),
        help_text=_("Categoria de receita usada quando o orçamento é aprovado."),
    )
    ativo = models.BooleanField(_("ativo"), default=True)

    class Meta:
        verbose_name = _("procedimento")
        verbose_name_plural = _("procedimentos")
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["clinica", "nome"], name="procedimento_unico"),
            models.CheckConstraint(condition=Q(valor__gte=0), name="procedimento_valor"),
        ]

    def __str__(self):
        return self.nome


class Orcamento(ModeloDaClinica):
    class Situacao(models.TextChoices):
        ABERTO = "aberto", _("Em aberto")
        APROVADO = "aprovado", _("Aprovado")
        RECUSADO = "recusado", _("Recusado")

    paciente = models.ForeignKey(
        "pacientes.Paciente",
        on_delete=models.PROTECT,
        related_name="orcamentos",
        verbose_name=_("paciente"),
    )
    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("profissional"),
    )
    data = models.DateField(_("data"), default=timezone.localdate)
    validade = models.DateField(_("válido até"), default=validade_padrao)
    situacao = models.CharField(
        _("situação"), max_length=10, choices=Situacao.choices, default=Situacao.ABERTO
    )
    desconto = models.DecimalField(_("desconto"), default=Decimal("0.00"), **DINHEIRO)
    observacoes = models.TextField(_("observações"), blank=True)
    lancamento = models.OneToOneField(
        "financeiro.Lancamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orcamento",
        verbose_name=_("lançamento a receber"),
    )
    decidido_em = models.DateTimeField(_("aprovado ou recusado em"), null=True, blank=True)
    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("aprovado ou recusado por"),
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("criado por"),
    )
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)
    alterado_em = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        verbose_name = _("orçamento")
        verbose_name_plural = _("orçamentos")
        ordering = ["-data", "-pk"]
        constraints = [
            models.CheckConstraint(condition=Q(desconto__gte=0), name="orcamento_desconto"),
        ]

    def __str__(self):
        return f"{self.pk} – {self.paciente}"

    @property
    def subtotal(self):
        return sum((item.total for item in self.itens.all()), start=Decimal("0.00"))

    @property
    def total(self):
        return max(self.subtotal - self.desconto, Decimal("0.00"))

    @property
    def vencido(self):
        return self.situacao == self.Situacao.ABERTO and self.validade < timezone.localdate()

    @property
    def dentes(self):
        """Every tooth in the estimate, for the dental chart."""
        return sorted({dente for item in self.itens.all() for dente in item.lista_dentes})


class ItemOrcamento(ModeloDaClinica):
    orcamento = models.ForeignKey(
        Orcamento, on_delete=models.CASCADE, related_name="itens", verbose_name=_("orçamento")
    )
    procedimento = models.ForeignKey(
        Procedimento,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("procedimento"),
    )
    descricao = models.CharField(_("descrição"), max_length=200)
    # FDI tooth numbers separated by commas ("11,12"); empty for the whole mouth.
    dentes = models.CharField(_("dentes"), max_length=200, blank=True)
    faces = models.CharField(
        _("faces ou região"),
        max_length=60,
        blank=True,
        help_text=_("Ex.: MOD, vestibular, arcada superior."),
    )
    quantidade = models.PositiveSmallIntegerField(_("quantidade"), default=1)
    valor_unitario = models.DecimalField(_("valor unitário"), **DINHEIRO)

    class Meta:
        verbose_name = _("item do orçamento")
        verbose_name_plural = _("itens do orçamento")
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(condition=Q(quantidade__gte=1), name="item_quantidade"),
            models.CheckConstraint(condition=Q(valor_unitario__gte=0), name="item_valor"),
        ]

    def __str__(self):
        return self.descricao

    @property
    def total(self):
        return self.valor_unitario * self.quantidade

    @property
    def dentes_exibicao(self):
        return ", ".join(str(d) for d in self.lista_dentes)

    @property
    def lista_dentes(self):
        return [int(d) for d in self.dentes.split(",") if d.strip().isdecimal()]
