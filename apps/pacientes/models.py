import datetime

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.isolamento import ClinicaDiferente, ModeloDaClinica


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


class PessoaRelacionada(ModeloDaClinica):
    """A relative or contact of a patient (decision 101, legacy `id_pessoas_relac`).

    Either another patient of the clinic (the link then shows on both records) or someone
    outside it, kept with just a name and a phone. A link grants no access to anything:
    it is only information on the registration.
    """

    class Vinculo(models.TextChoices):
        MAE = "mae", _("Mãe")
        PAI = "pai", _("Pai")
        RESPONSAVEL = "responsavel", _("Responsável legal")
        CONJUGE = "conjuge", _("Cônjuge")
        FILHO = "filho", _("Filho(a)")
        IRMAO = "irmao", _("Irmão(ã)")
        AVO = "avo", _("Avô/avó")
        NETO = "neto", _("Neto(a)")
        PARENTE = "parente", _("Outro parente")
        EMERGENCIA = "emergencia", _("Contato de emergência")
        CONTATO = "contato", _("Contato")

    paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        related_name="relacionados",
        verbose_name=_("paciente"),
    )
    vinculo = models.CharField(_("vínculo"), max_length=20, choices=Vinculo.choices)
    outro_paciente = models.ForeignKey(
        Paciente,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="relacionado_a",
        verbose_name=_("paciente da clínica"),
    )
    nome = models.CharField(_("nome"), max_length=200, blank=True)
    telefone = models.CharField(_("telefone"), max_length=11, blank=True)
    observacao = models.CharField(_("observação"), max_length=200, blank=True)
    criado_em = models.DateTimeField(_("criado em"), auto_now_add=True)

    class Meta:
        verbose_name = _("pessoa relacionada")
        verbose_name_plural = _("pessoas relacionadas")
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(outro_paciente__isnull=False) | ~models.Q(nome=""),
                name="relacionada_paciente_ou_nome",
            ),
            models.CheckConstraint(
                condition=~models.Q(outro_paciente=models.F("paciente")),
                name="relacionada_nao_e_o_proprio",
            ),
            models.UniqueConstraint(
                fields=["paciente", "outro_paciente", "vinculo"],
                name="relacionada_unica",
            ),
        ]

    def __str__(self):
        return f"{self.get_vinculo_display()}: {self.nome_exibido}"

    def save(self, *args, **kwargs):
        self._conferir_clinica()
        if self.clinica_id is None:  # without isolation (commands)
            self.clinica_id = self.paciente.clinica_id
        clinicas = {self.paciente.clinica_id}
        if self.outro_paciente_id:
            clinicas.add(self.outro_paciente.clinica_id)
        if clinicas != {self.clinica_id}:
            raise ClinicaDiferente("Both patients must be of this clinic.")
        super().save(*args, **kwargs)

    @property
    def nome_exibido(self):
        return self.outro_paciente.nome if self.outro_paciente_id else self.nome

    @property
    def telefone_exibido(self):
        if self.telefone or not self.outro_paciente_id:
            return self.telefone
        outro = self.outro_paciente
        return outro.whatsapp or outro.telefone_celular or outro.telefone_residencial
