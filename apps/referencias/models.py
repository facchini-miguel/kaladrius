"""Public reference tables shared by every clinic (not isolated per clinic).

Data comes from official sources (IBGE, Banco Central) and is loaded by migrations
from the JSON files in apps/referencias/dados/.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.ordem import ALFABETICA


class UF(models.Model):
    codigo = models.PositiveSmallIntegerField(_("código IBGE"), primary_key=True)
    sigla = models.CharField(_("sigla"), max_length=2, unique=True)
    nome = models.CharField(_("nome"), max_length=50)
    regiao = models.CharField(_("região"), max_length=20)

    class Meta:
        verbose_name = _("UF")
        verbose_name_plural = _("UFs")
        ordering = ["sigla"]

    def __str__(self):
        return self.sigla


class Cidade(models.Model):
    codigo = models.PositiveIntegerField(_("código IBGE"), primary_key=True)
    nome = models.CharField(_("nome"), max_length=100, db_collation=ALFABETICA)
    uf = models.ForeignKey(
        UF, on_delete=models.PROTECT, related_name="cidades", verbose_name=_("UF")
    )

    class Meta:
        verbose_name = _("cidade")
        verbose_name_plural = _("cidades")
        ordering = ["nome"]
        indexes = [models.Index(fields=["uf", "nome"], name="cidade_uf_nome")]

    def __str__(self):
        return f"{self.nome} - {self.uf.sigla}"


class Banco(models.Model):
    ispb = models.CharField(_("ISPB"), max_length=8, primary_key=True)
    codigo = models.PositiveSmallIntegerField(_("código"), null=True, blank=True, unique=True)
    nome = models.CharField(_("nome"), max_length=200, db_collation=ALFABETICA)
    nome_curto = models.CharField(_("nome curto"), max_length=100)

    class Meta:
        verbose_name = _("banco")
        verbose_name_plural = _("bancos")
        ordering = [models.F("codigo").asc(nulls_last=True), "nome"]

    def __str__(self):
        if self.codigo is None:
            return self.nome_curto
        return f"{self.codigo:03d} - {self.nome_curto}"


class EstadoCivil(models.Model):
    nome = models.CharField(_("nome"), max_length=30, unique=True, db_collation=ALFABETICA)
    ordem = models.PositiveSmallIntegerField(_("ordem"), default=0)

    class Meta:
        verbose_name = _("estado civil")
        verbose_name_plural = _("estados civis")
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome


class Bairro(models.Model):
    """Known neighborhoods of a city (decision 100): general address data, not about any
    person, suggested on the patient form. The first ones came from the legacy Odonto."""

    cidade = models.ForeignKey(
        Cidade, on_delete=models.CASCADE, related_name="bairros", verbose_name=_("cidade")
    )
    nome = models.CharField(_("nome"), max_length=100, db_collation=ALFABETICA)

    class Meta:
        verbose_name = _("bairro")
        verbose_name_plural = _("bairros")
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(fields=["cidade", "nome"], name="bairro_unico_por_cidade")
        ]

    def __str__(self):
        return self.nome


class Logradouro(models.Model):
    """A known street of a city, with its type in the name (\"Rua…\", \"Avenida…\")."""

    cidade = models.ForeignKey(
        Cidade, on_delete=models.CASCADE, related_name="logradouros", verbose_name=_("cidade")
    )
    bairro = models.ForeignKey(
        Bairro,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logradouros",
        verbose_name=_("bairro"),
    )
    nome = models.CharField(_("nome"), max_length=200, db_collation=ALFABETICA)

    class Meta:
        verbose_name = _("logradouro")
        verbose_name_plural = _("logradouros")
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["cidade", "bairro", "nome"], name="logradouro_unico_por_bairro"
            )
        ]

    def __str__(self):
        return self.nome
