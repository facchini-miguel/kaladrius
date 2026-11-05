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
    legal_name = models.CharField(
        _("razão social"), max_length=200, blank=True, db_column="razao_social"
    )
    # The country's document of an individual or a company (decision 121); the name stayed from
    # Brazil.
    tax_id = models.CharField(
        _("documento"),
        max_length=20,
        blank=True,
        help_text=_("Pode ser digitado com ou sem pontuação."),
        db_column="cpf_cnpj",
    )
    rg = models.CharField(_("RG"), max_length=20, blank=True)
    state_registration = models.CharField(
        _("inscrição estadual"), max_length=20, blank=True, db_column="inscricao_estadual"
    )
    sex = models.CharField(
        _("sexo"), max_length=1, choices=Sexo.choices, blank=True, db_column="sexo"
    )
    birth_date = models.DateField(
        _("data de nascimento"), null=True, blank=True, db_column="data_nascimento"
    )
    marital_status = models.ForeignKey(
        "referencias.MaritalStatus",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("estado civil"),
        db_column="estado_civil_id",
    )
    occupation = models.CharField(_("profissão"), max_length=100, blank=True, db_column="profissao")
    guardian = models.CharField(
        _("responsável"),
        max_length=200,
        blank=True,
        help_text=_("Para menores de idade, por exemplo."),
        db_column="responsavel",
    )

    mobile_phone = models.CharField(
        _("celular"), max_length=11, blank=True, db_column="telefone_celular"
    )
    # Fax and MSN from the legacy system are not kept as fields: nobody uses them anymore.
    whatsapp = models.CharField(
        _("WhatsApp"),
        max_length=11,
        blank=True,
        help_text=_("Com DDD. A ficha abre a conversa direto no WhatsApp."),
    )
    home_phone = models.CharField(
        _("telefone residencial"), max_length=11, blank=True, db_column="telefone_residencial"
    )
    work_phone = models.CharField(
        _("telefone comercial"), max_length=11, blank=True, db_column="telefone_comercial"
    )
    email = models.EmailField(_("e-mail"), blank=True)

    # Brazil: 8 digits; other countries (decision 117): up to a 9-digit ZIP+4.
    postal_code = models.CharField(_("CEP"), max_length=9, blank=True, db_column="cep")
    state = models.ForeignKey(
        "referencias.State",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("UF"),
        db_column="uf_id",
    )
    city = models.ForeignKey(
        "referencias.City",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("cidade"),
        db_column="cidade_id",
    )
    # Outside Brazil the national state and city tables (IBGE) do not apply: typed text.
    state_name = models.CharField(
        _("estado ou província"), max_length=60, blank=True, db_column="estado_nome"
    )
    city_name = models.CharField(_("cidade"), max_length=100, blank=True, db_column="cidade_nome")
    neighborhood = models.CharField(_("bairro"), max_length=100, blank=True, db_column="bairro")
    street = models.CharField(
        _("endereço"),
        max_length=200,
        blank=True,
        help_text=_("Rua, avenida…"),
        db_column="logradouro",
    )
    number = models.CharField(_("número"), max_length=10, blank=True, db_column="numero")
    complement = models.CharField(
        _("complemento"), max_length=100, blank=True, db_column="complemento"
    )

    notes = models.TextField(_("observações"), blank=True, db_column="observacoes")
    active = models.BooleanField(_("ativo"), default=True, db_column="ativo")
    # Archiving replaces deleting: the patient leaves every screen of the team but keeps
    # their history (schedule, recalls, audit). Only clinic administrators see archived
    # patients, and can restore them (decision 046).
    archived = models.BooleanField(_("arquivado"), default=False, db_column="arquivado")
    archived_at = models.DateTimeField(
        _("arquivado em"), null=True, blank=True, db_column="arquivado_em"
    )
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("arquivado por"),
        db_column="arquivado_por_id",
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
            models.Index(fields=["clinic", "tax_id"], name="paciente_clinica_cpf_cnpj"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["clinic", "tax_id"],
                condition=~models.Q(tax_id=""),
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
        if self.birth_date is None:
            return None
        today = datetime.date.today()
        nascimento = self.birth_date
        return (
            today.year
            - nascimento.year
            - ((today.month, today.day) < (nascimento.month, nascimento.day))
        )

    @property
    def cidade_estado(self):
        """City and state as written on the record: from the national tables in Brazil, typed
        anywhere else (decision 117)."""
        if self.city_id:
            return f"{self.city.name}/{self.city.state.abbreviation}"
        return ", ".join(parte for parte in (self.city_name, self.state_name) if parte)

    @property
    def telefone_principal(self):
        return self.mobile_phone or self.home_phone or self.work_phone


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
    relationship = models.CharField(
        _("vínculo"), max_length=20, choices=Relationship.choices, db_column="vinculo"
    )
    other_patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="relacionado_a",
        verbose_name=_("paciente da clínica"),
        db_column="outro_paciente_id",
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
                condition=models.Q(other_patient__isnull=False) | ~models.Q(name=""),
                name="relacionada_paciente_ou_nome",
            ),
            models.CheckConstraint(
                condition=~models.Q(other_patient=models.F("patient")),
                name="relacionada_nao_e_o_proprio",
            ),
            models.UniqueConstraint(
                fields=["patient", "other_patient", "relationship"],
                name="relacionada_unica",
            ),
        ]

    def __str__(self):
        return f"{self.get_relationship_display()}: {self.nome_exibido}"

    def save(self, *args, **kwargs):
        self._conferir_clinica()
        if self.clinic_id is None:  # without isolation (commands)
            self.clinic_id = self.patient.clinic_id
        clinicas = {self.patient.clinic_id}
        if self.other_patient_id:
            clinicas.add(self.other_patient.clinic_id)
        if clinicas != {self.clinic_id}:
            raise ClinicaDiferente("Both patients must be of this clinic.")
        super().save(*args, **kwargs)

    @property
    def nome_exibido(self):
        return self.other_patient.name if self.other_patient_id else self.name

    @property
    def telefone_exibido(self):
        if self.phone or not self.other_patient_id:
            return self.phone
        other = self.other_patient
        return other.whatsapp or other.mobile_phone or other.home_phone
