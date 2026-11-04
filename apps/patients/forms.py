import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core import countries, identification
from apps.core.forms import FormularioBootstrap, campo_documento, documento_por_tipo
from apps.core.validators import normalizar_telefone
from apps.reference_data.models import City, State

from .models import Patient, RelatedPerson


class UFField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.sigla} - {obj.nome}"


class CidadeField(forms.ModelChoiceField):
    """City select labeled by name only (the state is chosen in the field beside it)."""

    def label_from_instance(self, obj):
        return obj.nome


def _campo_texto(label, max_length, **attrs):
    """Optional text field that accepts punctuation; the value is normalized in clean_*()."""
    return forms.CharField(
        label=label,
        max_length=max_length,
        required=False,
        widget=forms.TextInput(attrs=attrs),
    )


class PacienteForm(FormularioBootstrap, forms.ModelForm):
    uf = UFField(queryset=State.objects.all(), required=False, label=_("UF"))
    cidade = CidadeField(queryset=City.objects.none(), required=False, label=_("Cidade"))
    # The country's document (decision 121), typed with punctuation, stored compact.
    cpf_cnpj = campo_documento()
    cep = _campo_texto(_("CEP"), 10)
    telefone_celular = _campo_texto(_("Celular"), 16, inputmode="tel")
    whatsapp = _campo_texto(_("WhatsApp"), 16, inputmode="tel")
    telefone_residencial = _campo_texto(_("Telefone residencial"), 16, inputmode="tel")
    telefone_comercial = _campo_texto(_("Telefone comercial"), 16, inputmode="tel")

    class Meta:
        model = Patient
        fields = [
            "tipo",
            "nome",
            "razao_social",
            "cpf_cnpj",
            "inscricao_estadual",
            "rg",
            "sexo",
            "data_nascimento",
            "estado_civil",
            "profissao",
            "responsavel",
            "telefone_celular",
            "whatsapp",
            "telefone_residencial",
            "telefone_comercial",
            "email",
            "cep",
            "uf",
            "cidade",
            "estado_nome",
            "cidade_nome",
            "bairro",
            "logradouro",
            "numero",
            "complemento",
            "observacoes",
            "ativo",
        ]
        widgets = {
            "tipo": forms.RadioSelect,
            "data_nascimento": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "observacoes": forms.Textarea(attrs={"rows": 4}),
        }

    # Brazilian fields; outside Brazil the state and city are typed (decision 117) and the
    # document is the country's (decision 121).
    SO_NO_BRASIL = ["inscricao_estadual", "rg", "uf", "cidade"]
    FORA_DO_BRASIL = ["estado_nome", "cidade_nome"]

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinic_id is None:
            self.instance.clinic = clinic
        self.pais = countries.pais_da_clinica(clinic)
        self.fields["cep"].label = countries.rotulo_cep(self.pais)
        self.documentos = identification.do_pais(self.pais)
        documento_por_tipo(
            self.fields["cpf_cnpj"],
            self.documentos.paciente,
            self.documentos.empresa,
            self["tipo"].value(),
        )
        for campo in self.FORA_DO_BRASIL if self.pais == "BR" else self.SO_NO_BRASIL:
            del self.fields[campo]
        if self.pais != "BR":
            return
        self.fields["cep"].widget.attrs["inputmode"] = "numeric"

        # Chained selects: the city list depends on the chosen state (HTMX).
        self.fields["uf"].widget.attrs.update(
            {
                "hx-get": reverse("reference_data:city_options"),
                "hx-target": "#id_cidade",
                "hx-trigger": "change",
            }
        )
        # Known neighborhoods and streets of the chosen city as suggestions (decision 100);
        # anything else can still be typed.
        self.fields["cidade"].widget.attrs.update(
            {
                "hx-get": reverse("reference_data:address_suggestions"),
                "hx-target": "#sugestoes-endereco",
                "hx-trigger": "load, change",
            }
        )
        for campo, lista in (
            ("bairro", "bairros-sugeridos"),
            ("logradouro", "logradouros-sugeridos"),
        ):
            self.fields[campo].widget.attrs.update({"list": lista, "autocomplete": "off"})
        uf_id = self.data.get(self.add_prefix("uf")) if self.is_bound else self.instance.uf_id
        self.fields["cidade"].queryset = (
            City.objects.filter(uf_id=int(uf_id))
            if str(uf_id or "").isdecimal()
            else City.objects.none()
        )

    def clean_cep(self):
        return countries.normalizar_cep(self.cleaned_data.get("cep"), self.pais)

    def _limpar_telefone(self, nome):
        return normalizar_telefone(self.cleaned_data.get(nome), self.pais)

    def clean_telefone_celular(self):
        return self._limpar_telefone("telefone_celular")

    def clean_whatsapp(self):
        return self._limpar_telefone("whatsapp")

    def clean_telefone_residencial(self):
        return self._limpar_telefone("telefone_residencial")

    def clean_telefone_comercial(self):
        return self._limpar_telefone("telefone_comercial")

    def clean_data_nascimento(self):
        data = self.cleaned_data.get("data_nascimento")
        if data and data > datetime.date.today():
            raise forms.ValidationError(_("A data de nascimento não pode estar no futuro."))
        return data

    def clean(self):
        dados = super().clean()
        tipo = dados.get("tipo")
        # Checked here because it depends on the person type; a type without a document in
        # this country (an individual in the United States) keeps none.
        do_tipo = (
            self.documentos.empresa if tipo == Patient.Tipo.JURIDICA else self.documentos.paciente
        )
        documento = ""
        if do_tipo is not None:
            try:
                documento = identification.limpar(
                    dados.get("cpf_cnpj", ""), [do_tipo], do_tipo.sigla
                )
            except ValidationError as erro:
                self.add_error("cpf_cnpj", erro)
        if "cpf_cnpj" in dados:
            dados["cpf_cnpj"] = documento

        if documento:
            # The clinic is not a form field, so the unique constraint is checked here.
            outro = Patient.objects.filter(cpf_cnpj=documento).exclude(pk=self.instance.pk).first()
            if outro is not None and outro.arquivado:
                self.add_error(
                    "cpf_cnpj",
                    _(
                        "Este documento é de um paciente arquivado. Peça ao administrador "
                        "da clínica para restaurá-lo."
                    ),
                )
            elif outro is not None:
                self.add_error(
                    "cpf_cnpj", _("Já existe um paciente com este documento nesta clínica.")
                )

        # Fields that only make sense for one person type are cleared for the other.
        if tipo == Patient.Tipo.JURIDICA:
            for campo in ["rg", "sexo", "estado_civil", "profissao", "responsavel"]:
                dados[campo] = None if campo == "estado_civil" else ""
            dados["data_nascimento"] = None
        else:
            dados["razao_social"] = ""
            dados["inscricao_estadual"] = ""

        cidade, uf = dados.get("cidade"), dados.get("uf")
        if cidade is not None and cidade.uf_id != getattr(uf, "pk", None):
            self.add_error("cidade", _("A cidade não pertence à UF escolhida."))
        return dados


class PessoaRelacionadaForm(FormularioBootstrap, forms.ModelForm):
    """A relative or contact (decision 101): another patient of the clinic, or a name."""

    telefone = _campo_texto(_("Telefone"), 16, inputmode="tel")

    class Meta:
        model = RelatedPerson
        fields = ["vinculo", "outro_paciente", "nome", "telefone", "observacao"]
        widgets = {"outro_paciente": forms.HiddenInput}
        help_texts = {"nome": _("Só para quem não é paciente da clínica.")}

    def __init__(self, *args, paciente, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.paciente = paciente
        if self.instance.clinic_id is None:
            self.instance.clinic_id = paciente.clinic_id
        self.fields["outro_paciente"].queryset = Patient.objects.exclude(pk=paciente.pk)

    def clean_telefone(self):
        return normalizar_telefone(self.cleaned_data.get("telefone"))

    def clean(self):
        dados = super().clean()
        outro, nome = dados.get("outro_paciente"), dados.get("nome", "").strip()
        if outro and nome:
            self.add_error("nome", _("Escolha um paciente ou digite um nome, não os dois."))
        elif not outro and not nome:
            self.add_error("nome", _("Escolha um paciente da clínica ou digite o nome."))
        dados["nome"] = nome
        if (
            outro
            and RelatedPerson.objects.filter(
                paciente=self.instance.paciente, outro_paciente=outro, vinculo=dados.get("vinculo")
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error("outro_paciente", _("Este vínculo já está cadastrado."))
        return dados
