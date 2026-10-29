"""The medical record (0.29.0, decision 081): one anamnesis per visit.

Written and read only by practitioners. Once finalized, a visit never changes: corrections
are addenda, with their own date and author. Nothing here is ever deleted (the record is
kept for 20 years), so patients with a medical record cannot be permanently deleted.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.agenda.models import Agendamento
from apps.core.isolamento import ModeloDaClinica
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

# The anamnesis fields, in the order they are written and shown.
CAMPOS_DA_ANAMNESE = ["queixa_principal", "historia", "antecedentes", "exame_fisico", "conduta"]


class Atendimento(ModeloDaClinica):
    paciente = models.ForeignKey(
        Paciente, on_delete=models.PROTECT, related_name="atendimentos", verbose_name=_("paciente")
    )
    profissional = models.ForeignKey(
        Profissional,
        on_delete=models.PROTECT,
        related_name="atendimentos",
        verbose_name=_("profissional"),
    )
    agendamento = models.OneToOneField(
        Agendamento,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="atendimento",
        verbose_name=_("agendamento"),
    )
    data = models.DateTimeField(_("data do atendimento"), default=timezone.now)
    queixa_principal = models.TextField(_("queixa principal"), blank=True)
    historia = models.TextField(_("história da doença atual"), blank=True)
    antecedentes = models.TextField(
        _("antecedentes"),
        blank=True,
        help_text=_("Pessoais e familiares, medicamentos em uso, alergias."),
    )
    exame_fisico = models.TextField(_("exame físico"), blank=True)
    conduta = models.TextField(_("conduta e plano"), blank=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    alterado_em = models.DateTimeField(auto_now=True)
    finalizado_em = models.DateTimeField(_("finalizado em"), null=True, blank=True)
    finalizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = _("atendimento")
        verbose_name_plural = _("atendimentos")
        ordering = ["-data", "-pk"]

    def __str__(self):
        return f"{self.paciente} – {timezone.localtime(self.data):%d/%m/%Y %H:%M}"

    @property
    def finalizado(self):
        return self.finalizado_em is not None


class Adendo(ModeloDaClinica):
    """A correction or note added to a finalized visit, which itself never changes."""

    atendimento = models.ForeignKey(
        Atendimento, on_delete=models.PROTECT, related_name="adendos", verbose_name=_("atendimento")
    )
    texto = models.TextField(_("adendo"))
    profissional = models.ForeignKey(
        Profissional, on_delete=models.PROTECT, related_name="+", verbose_name=_("profissional")
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("adendo")
        verbose_name_plural = _("adendos")
        ordering = ["criado_em", "pk"]

    def __str__(self):
        return f"{self.atendimento} – {_('adendo')}"


class Atestado(ModeloDaClinica):
    """A medical certificate issued in a visit (0.30.0, decision 082). Never changed or
    deleted after issued; it can be printed again."""

    class Tipo(models.TextChoices):
        COMPARECIMENTO = "comparecimento", _("Comparecimento")
        AFASTAMENTO = "afastamento", _("Afastamento")

    atendimento = models.ForeignKey(
        Atendimento,
        on_delete=models.PROTECT,
        related_name="atestados",
        verbose_name=_("atendimento"),
    )
    tipo = models.CharField(
        _("tipo"), max_length=20, choices=Tipo.choices, default=Tipo.COMPARECIMENTO
    )
    data = models.DateField(_("data do atendimento"), default=timezone.localdate)
    hora_inicio = models.TimeField(_("das"), null=True, blank=True)
    hora_fim = models.TimeField(_("às"), null=True, blank=True)
    dias = models.PositiveSmallIntegerField(
        _("dias de afastamento"), null=True, blank=True, help_text=_("Só para afastamento.")
    )
    observacao = models.TextField(
        _("observações"),
        blank=True,
        help_text=_("Aparece no atestado. Por exemplo: deve permanecer em repouso."),
    )
    profissional = models.ForeignKey(
        Profissional, on_delete=models.PROTECT, related_name="+", verbose_name=_("profissional")
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("atestado")
        verbose_name_plural = _("atestados")
        ordering = ["criado_em", "pk"]

    def __str__(self):
        return f"{self.atendimento} – {self.get_tipo_display()}"


class Receita(ModeloDaClinica):
    """A simple prescription issued in a visit (0.30.0, decision 082): free text, one item
    per line. Controlled drugs need the official forms, which the system does not issue."""

    atendimento = models.ForeignKey(
        Atendimento,
        on_delete=models.PROTECT,
        related_name="receitas",
        verbose_name=_("atendimento"),
    )
    prescricao = models.TextField(
        _("medicamentos e como usar"),
        help_text=_("Um item por linha: medicamento, dose e como usar."),
    )
    profissional = models.ForeignKey(
        Profissional, on_delete=models.PROTECT, related_name="+", verbose_name=_("profissional")
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        # "Receita" is also revenue in Finance: a context keeps the translations apart.
        verbose_name = pgettext_lazy("prescrição", "receita")
        verbose_name_plural = pgettext_lazy("prescrição", "receitas")
        ordering = ["criado_em", "pk"]

    def __str__(self):
        return f"{self.atendimento} – {pgettext_lazy('prescrição', 'receita')}"


class PedidoDeExames(ModeloDaClinica):
    """An exam request issued in a visit (0.31.0, decision 083): one exam per line."""

    atendimento = models.ForeignKey(
        Atendimento,
        on_delete=models.PROTECT,
        related_name="pedidos_de_exames",
        verbose_name=_("atendimento"),
    )
    exames = models.TextField(_("exames"), help_text=_("Um exame por linha."))
    indicacao = models.TextField(
        _("indicação clínica"), blank=True, help_text=_("Aparece no pedido.")
    )
    profissional = models.ForeignKey(
        Profissional, on_delete=models.PROTECT, related_name="+", verbose_name=_("profissional")
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("pedido de exames")
        verbose_name_plural = _("pedidos de exames")
        ordering = ["criado_em", "pk"]

    def __str__(self):
        return f"{self.atendimento} – {_('pedido de exames')}"


class Anexo(ModeloDaClinica):
    """A file kept in a visit: exam results, photos, reports (0.31.0, decision 083).

    Stored in the database, so the daily backup and the weekly restore test cover it, and
    only ever served through a view that checks the user is a practitioner.
    """

    atendimento = models.ForeignKey(
        Atendimento, on_delete=models.PROTECT, related_name="anexos", verbose_name=_("atendimento")
    )
    descricao = models.CharField(
        _("descrição"), max_length=200, blank=True, help_text=_("Por exemplo: hemograma de março.")
    )
    nome = models.CharField(_("arquivo"), max_length=255)
    tipo = models.CharField(max_length=50)
    tamanho = models.PositiveIntegerField()
    conteudo = models.BinaryField()
    profissional = models.ForeignKey(
        Profissional, on_delete=models.PROTECT, related_name="+", verbose_name=_("profissional")
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("anexo")
        verbose_name_plural = _("anexos")
        ordering = ["criado_em", "pk"]

    def __str__(self):
        return f"{self.atendimento} – {self.descricao or self.nome}"
