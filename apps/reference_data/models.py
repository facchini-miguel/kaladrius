"""Public reference tables shared by every clinic (not isolated per clinic).

Data comes from official sources (IBGE, Banco Central) and is loaded by migrations
from the JSON files in apps/reference_data/data/.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.ordering import ALPHABETICAL


class State(models.Model):
    code = models.PositiveSmallIntegerField(_("código IBGE"), primary_key=True)
    abbreviation = models.CharField(_("sigla"), max_length=2, unique=True)
    name = models.CharField(_("nome"), max_length=50)
    region = models.CharField(_("região"), max_length=20)

    class Meta:
        db_table = "reference_data_state"
        verbose_name = _("UF")
        verbose_name_plural = _("UFs")
        ordering = ["abbreviation"]

    def __str__(self):
        return self.abbreviation


class City(models.Model):
    code = models.PositiveIntegerField(_("código IBGE"), primary_key=True)
    name = models.CharField(_("nome"), max_length=100, db_collation=ALPHABETICAL)
    state = models.ForeignKey(
        State,
        on_delete=models.PROTECT,
        related_name="cities",
        verbose_name=_("UF"),
    )

    class Meta:
        db_table = "reference_data_city"
        verbose_name = _("cidade")
        verbose_name_plural = _("cidades")
        ordering = ["name"]
        indexes = [models.Index(fields=["state", "name"], name="city_state_name")]

    def __str__(self):
        return f"{self.name} - {self.state.abbreviation}"


class Bank(models.Model):
    ispb = models.CharField(_("ISPB"), max_length=8, primary_key=True)
    code = models.PositiveSmallIntegerField(_("código"), null=True, blank=True, unique=True)
    name = models.CharField(_("nome"), max_length=200, db_collation=ALPHABETICAL)
    short_name = models.CharField(_("nome curto"), max_length=100)

    class Meta:
        db_table = "reference_data_bank"
        verbose_name = _("banco")
        verbose_name_plural = _("bancos")
        ordering = [models.F("code").asc(nulls_last=True), "name"]

    def __str__(self):
        if self.code is None:
            return self.short_name
        return f"{self.code:03d} - {self.short_name}"


class MaritalStatus(models.Model):
    name = models.CharField(_("nome"), max_length=30, unique=True, db_collation=ALPHABETICAL)
    sort_order = models.PositiveSmallIntegerField(_("ordem"), default=0)

    class Meta:
        db_table = "reference_data_marital_status"
        verbose_name = _("estado civil")
        verbose_name_plural = _("estados civis")
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Neighborhood(models.Model):
    """Known neighborhoods of a city (decision 100): general address data, not about any
    person, suggested on the patient form. The first ones came from the legacy Odonto."""

    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name="neighborhoods",
        verbose_name=_("cidade"),
    )
    name = models.CharField(_("nome"), max_length=100, db_collation=ALPHABETICAL)

    class Meta:
        db_table = "reference_data_neighborhood"
        verbose_name = _("bairro")
        verbose_name_plural = _("bairros")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["city", "name"], name="neighborhood_unique_per_city")
        ]

    def __str__(self):
        return self.name


class Street(models.Model):
    """A known street of a city, with its type in the name (\"Rua…\", \"Avenida…\")."""

    city = models.ForeignKey(
        City,
        on_delete=models.CASCADE,
        related_name="streets",
        verbose_name=_("cidade"),
    )
    neighborhood = models.ForeignKey(
        Neighborhood,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="streets",
        verbose_name=_("bairro"),
    )
    name = models.CharField(_("nome"), max_length=200, db_collation=ALPHABETICAL)

    class Meta:
        db_table = "reference_data_street"
        verbose_name = _("logradouro")
        verbose_name_plural = _("logradouros")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["city", "neighborhood", "name"], name="street_unique_per_neighborhood"
            )
        ]

    def __str__(self):
        return self.name
