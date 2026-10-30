import datetime

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.isolamento import ModeloDaClinica


class Paciente(ModeloDaClinica):
    """A patient: an individual (CPF) or a company (CNPJ)."""

    class Tipo(models.TextChoices):
        FISICA = "PF", _("Pessoa física")
        JURIDICA = "PJ", _("Pessoa jurídica")

    class Sexo(models.TextChoices):
        FEMININO = "F", _("Feminino")
        MASCULINO = "M", _("Masculino")
        OUTRO = "O", _("Outro")

    tipo = models.CharField(_("tipo"), max_length=2, choices=Tipo.choices, default=Tipo.FISICA)
    nome = models.CharField(
        _("nome"), max_length=200, help_text=_("Para pessoa jurídica, o nome fantasia.")
    )
    razao_social = models.CharField(_("razão social"), max_length=200, blank=True)
    cpf_cnpj = models.CharField(
        _("CPF/CNPJ"),
        max_length=14,
        blank=True,
        help_text=_("Pode ser digitado com ou sem pontuação."),
    )
    rg = models.CharField(_("RG"), max_length=20, blank=True)
    inscricao_estadual = models.CharField(_("inscrição estadual"), max_length=20, blank=True)
    sexo = models.CharField(_("sexo"), max_length=1, choices=Sexo.choices, blank=True)
    data_nascimento = models.DateField(_("data de nascimento"), null=True, blank=True)
    estado_civil = models.ForeignKey(
        "referencias.EstadoCivil",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("estado civil"),
    )
    profissao = models.CharField(_("profissão"), max_length=100, blank=True)
    responsavel = models.CharField(
        _("responsável"),
        max_length=200,
        blank=True,
        help_text=_("Para menores de idade, por exemplo."),
    )

    telefone_celular = models.CharField(_("celular"), max_length=11, blank=True)
    # Fax and MSN from the legacy system are not kept as fields: nobody uses them anymore.
    whatsapp = models.CharField(
        _("WhatsApp"),
        max_length=11,
        blank=True,
        help_text=_("Com DDD. A ficha abre a conversa direto no WhatsApp."),
    )
    telefone_residencial = models.CharField(_("telefone residencial"), max_length=11, blank=True)
    telefone_comercial = models.CharField(_("telefone comercial"), max_length=11, blank=True)
    email = models.EmailField(_("e-mail"), blank=True)

    cep = models.CharField(_("CEP"), max_length=8, blank=True)
    uf = models.ForeignKey(
        "referencias.UF",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("UF"),
    )
    cidade = models.ForeignKey(
        "referencias.Cidade",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("cidade"),
    )
    bairro = models.CharField(_("bairro"), max_length=100, blank=True)
    logradouro = models.CharField(
        _("endereço"), max_length=200, blank=True, help_text=_("Rua, avenida…")
    )
    numero = models.CharField(_("número"), max_length=10, blank=True)
    complemento = models.CharField(_("complemento"), max_length=100, blank=True)

    observacoes = models.TextField(_("observações"), blank=True)
    ativo = models.BooleanField(_("ativo"), default=True)
    # Archiving replaces deleting: the patient leaves every screen of the team but keeps
    # their history (schedule, recalls, audit). Only clinic administrators see archived
    # patients, and can restore them (decision 046).
    arquivado = models.BooleanField(_("arquivado"), default=False)
    arquivado_em = models.DateTimeField(_("arquivado em"), null=True, blank=True)
    arquivado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("arquivado por"),
    )
    criado_em = models.DateTimeField(_("cadastrado em"), auto_now_add=True)
    alterado_em = models.DateTimeField(_("alterado em"), auto_now=True)

    class Meta:
        verbose_name = _("paciente")
        verbose_name_plural = _("pacientes")
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["clinica", "nome"], name="paciente_clinica_nome"),
            models.Index(fields=["clinica", "cpf_cnpj"], name="paciente_clinica_cpf_cnpj"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["clinica", "cpf_cnpj"],
                condition=~models.Q(cpf_cnpj=""),
                name="paciente_cpf_cnpj_unico_por_clinica",
            ),
        ]

    def __str__(self):
        return self.nome

    @property
    def idade(self):
        """Age in whole years, or None when the birth date is unknown."""
        if self.data_nascimento is None:
            return None
        hoje = datetime.date.today()
        nascimento = self.data_nascimento
        return (
            hoje.year
            - nascimento.year
            - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
        )

    @property
    def telefone_principal(self):
        return self.telefone_celular or self.telefone_residencial or self.telefone_comercial
