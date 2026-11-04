import datetime

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.isolation import ClinicaDiferente, ModeloDaClinica
from apps.core.ordering import ALFABETICA


class Patient(ModeloDaClinica):
    """A patient: an individual (CPF) or a company (CNPJ)."""

    class Tipo(models.TextChoices):
        FISICA = "PF", _("Pessoa física")
        JURIDICA = "PJ", _("Pessoa jurídica")

    class Sexo(models.TextChoices):
        FEMININO = "F", _("Feminino")
        MASCULINO = "M", _("Masculino")
        OUTRO = "O", _("Outro")

    kind = models.CharField(
        _("tipo"), max_length=2, choices=Tipo.choices, default=Tipo.FISICA, db_column="tipo"
    )
    name = models.CharField(
        _("nome"),
        max_length=200,
        help_text=_("Para pessoa jurídica, o nome fantasia."),
        db_collation=ALFABETICA,
        db_column="nome",
    )
    razao_social = models.CharField(_("razão social"), max_length=200, blank=True)
    # The country's document of an individual or a company (decision 121); the name stayed from
    # Brazil.
    cpf_cnpj = models.CharField(
        _("documento"),
        max_length=20,
        blank=True,
        help_text=_("Pode ser digitado com ou sem pontuação."),
    )
    rg = models.CharField(_("RG"), max_length=20, blank=True)
    inscricao_estadual = models.CharField(_("inscrição estadual"), max_length=20, blank=True)
    sexo = models.CharField(_("sexo"), max_length=1, choices=Sexo.choices, blank=True)
    data_nascimento = models.DateField(_("data de nascimento"), null=True, blank=True)
    estado_civil = models.ForeignKey(
        "referencias.MaritalStatus",
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

    # Brazil: 8 digits; other countries (decision 117): up to a 9-digit ZIP+4.
    cep = models.CharField(_("CEP"), max_length=9, blank=True)
    uf = models.ForeignKey(
        "referencias.State",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("UF"),
    )
    cidade = models.ForeignKey(
        "referencias.City",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("cidade"),
    )
    # Outside Brazil the national state and city tables (IBGE) do not apply: typed text.
    estado_nome = models.CharField(_("estado ou província"), max_length=60, blank=True)
    cidade_nome = models.CharField(_("cidade"), max_length=100, blank=True)
    bairro = models.CharField(_("bairro"), max_length=100, blank=True)
    logradouro = models.CharField(
        _("endereço"), max_length=200, blank=True, help_text=_("Rua, avenida…")
    )
    number = models.CharField(_("número"), max_length=10, blank=True, db_column="numero")
    complemento = models.CharField(_("complemento"), max_length=100, blank=True)

    notes = models.TextField(_("observações"), blank=True, db_column="observacoes")
    active = models.BooleanField(_("ativo"), default=True, db_column="ativo")
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
    created_at = models.DateTimeField(_("cadastrado em"), auto_now_add=True, db_column="criado_em")
    updated_at = models.DateTimeField(_("alterado em"), auto_now=True, db_column="alterado_em")

    class Meta:
        db_table = "pacientes_paciente"
        verbose_name = _("paciente")
        verbose_name_plural = _("pacientes")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["clinic", "name"], name="paciente_clinica_nome"),
            models.Index(fields=["clinic", "cpf_cnpj"], name="paciente_clinica_cpf_cnpj"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "cpf_cnpj"],
                condition=~models.Q(cpf_cnpj=""),
                name="paciente_cpf_cnpj_unico_por_clinica",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def papel_documento(self):
        """Its document's role in apps/core/identification.py."""
        return "empresa" if self.kind == self.Tipo.JURIDICA else "paciente"

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
    def cidade_estado(self):
        """City and state as written on the record: from the national tables in Brazil, typed
        anywhere else (decision 117)."""
        if self.cidade_id:
            return f"{self.cidade.name}/{self.cidade.uf.sigla}"
        return ", ".join(parte for parte in (self.cidade_nome, self.estado_nome) if parte)

    @property
    def telefone_principal(self):
        return self.telefone_celular or self.telefone_residencial or self.telefone_comercial


class RelatedPerson(ModeloDaClinica):
    """A relative or contact of a patient (decision 101, legacy `id_pessoas_relac`).

    Either another patient of the clinic (the link then shows on both records) or someone
    outside it, kept with just a name and a phone. A link grants no access to anything:
    it is only information on the registration.
    """

    class Relationship(models.TextChoices):
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

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="relacionados",
        verbose_name=_("paciente"),
        db_column="paciente_id",
    )
    vinculo = models.CharField(_("vínculo"), max_length=20, choices=Relationship.choices)
    outro_paciente = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="relacionado_a",
        verbose_name=_("paciente da clínica"),
    )
    name = models.CharField(_("nome"), max_length=200, blank=True, db_column="nome")
    phone = models.CharField(_("telefone"), max_length=11, blank=True, db_column="telefone")
    note = models.CharField(_("observação"), max_length=200, blank=True, db_column="observacao")
    created_at = models.DateTimeField(_("criado em"), auto_now_add=True, db_column="criado_em")

    class Meta:
        db_table = "pacientes_pessoarelacionada"
        verbose_name = _("pessoa relacionada")
        verbose_name_plural = _("pessoas relacionadas")
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(outro_paciente__isnull=False) | ~models.Q(name=""),
                name="relacionada_paciente_ou_nome",
            ),
            models.CheckConstraint(
                condition=~models.Q(outro_paciente=models.F("patient")),
                name="relacionada_nao_e_o_proprio",
            ),
            models.UniqueConstraint(
                fields=["patient", "outro_paciente", "vinculo"],
                name="relacionada_unica",
            ),
        ]

    def __str__(self):
        return f"{self.get_vinculo_display()}: {self.nome_exibido}"

    def save(self, *args, **kwargs):
        self._conferir_clinica()
        if self.clinic_id is None:  # without isolation (commands)
            self.clinic_id = self.patient.clinic_id
        clinicas = {self.patient.clinic_id}
        if self.outro_paciente_id:
            clinicas.add(self.outro_paciente.clinic_id)
        if clinicas != {self.clinic_id}:
            raise ClinicaDiferente("Both patients must be of this clinic.")
        super().save(*args, **kwargs)

    @property
    def nome_exibido(self):
        return self.outro_paciente.name if self.outro_paciente_id else self.name

    @property
    def telefone_exibido(self):
        if self.phone or not self.outro_paciente_id:
            return self.phone
        outro = self.outro_paciente
        return outro.whatsapp or outro.telefone_celular or outro.telefone_residencial
