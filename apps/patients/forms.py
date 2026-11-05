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
        return f"{obj.abbreviation} - {obj.name}"


class CidadeField(forms.ModelChoiceField):
    """City select labeled by name only (the state is chosen in the field beside it)."""

    def label_from_instance(self, obj):
        return obj.name


def _campo_texto(label, max_length, **attrs):
    """Optional text field that accepts punctuation; the value is normalized in clean_*()."""
    return forms.CharField(
        label=label,
        max_length=max_length,
        required=False,
        widget=forms.TextInput(attrs=attrs),
    )


class PacienteForm(FormularioBootstrap, forms.ModelForm):
    state = UFField(queryset=State.objects.all(), required=False, label=_("UF"))
    city = CidadeField(queryset=City.objects.none(), required=False, label=_("Cidade"))
    # The country's document (decision 121), typed with punctuation, stored compact.
    tax_id = campo_documento()
    postal_code = _campo_texto(_("CEP"), 10)
    mobile_phone = _campo_texto(_("Celular"), 16, inputmode="tel")
    whatsapp = _campo_texto(_("WhatsApp"), 16, inputmode="tel")
    home_phone = _campo_texto(_("Telefone residencial"), 16, inputmode="tel")
    work_phone = _campo_texto(_("Telefone comercial"), 16, inputmode="tel")

    class Meta:
        model = Patient
        fields = [
            "kind",
            "name",
            "legal_name",
            "tax_id",
            "state_registration",
            "rg",
            "sex",
            "birth_date",
            "marital_status",
            "occupation",
            "guardian",
            "mobile_phone",
            "whatsapp",
            "home_phone",
            "work_phone",
            "email",
            "postal_code",
            "state",
            "city",
            "state_name",
            "city_name",
            "neighborhood",
            "street",
            "number",
            "complement",
            "notes",
            "active",
        ]
        widgets = {
            "kind": forms.RadioSelect,
            "birth_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    # Brazilian fields; outside Brazil the state and city are typed (decision 117) and the
    # document is the country's (decision 121).
    SO_NO_BRASIL = ["state_registration", "rg", "state", "city"]
    FORA_DO_BRASIL = ["state_name", "city_name"]

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinic_id is None:
            self.instance.clinic = clinic
        self.country = countries.pais_da_clinica(clinic)
        self.fields["postal_code"].label = countries.rotulo_cep(self.country)
        self.documentos = identification.do_pais(self.country)
        documento_por_tipo(
            self.fields["tax_id"],
            self.documentos.paciente,
            self.documentos.empresa,
            self["kind"].value(),
        )
        for campo in self.FORA_DO_BRASIL if self.country == "BR" else self.SO_NO_BRASIL:
            del self.fields[campo]
        if self.country != "BR":
            return
        self.fields["postal_code"].widget.attrs["inputmode"] = "numeric"

        # Chained selects: the city list depends on the chosen state (HTMX).
        self.fields["state"].widget.attrs.update(
            {
                "hx-get": reverse("reference_data:city_options"),
                "hx-target": "#id_cidade",
                "hx-trigger": "change",
            }
        )
        # Known neighborhoods and streets of the chosen city as suggestions (decision 100);
        # anything else can still be typed.
        self.fields["city"].widget.attrs.update(
            {
                "hx-get": reverse("reference_data:address_suggestions"),
                "hx-target": "#sugestoes-endereco",
                "hx-trigger": "load, change",
            }
        )
        for campo, lista in (
            ("neighborhood", "bairros-sugeridos"),
            ("street", "logradouros-sugeridos"),
        ):
            self.fields[campo].widget.attrs.update({"list": lista, "autocomplete": "off"})
        state_id = (
            self.data.get(self.add_prefix("state")) if self.is_bound else self.instance.state_id
        )
        self.fields["city"].queryset = (
            City.objects.filter(state_id=int(state_id))
            if str(state_id or "").isdecimal()
            else City.objects.none()
        )

    def clean_postal_code(self):
        return countries.normalizar_cep(self.cleaned_data.get("postal_code"), self.country)

    def _limpar_telefone(self, name):
        return normalizar_telefone(self.cleaned_data.get(name), self.country)

    def clean_mobile_phone(self):
        return self._limpar_telefone("mobile_phone")

    def clean_whatsapp(self):
        return self._limpar_telefone("whatsapp")

    def clean_home_phone(self):
        return self._limpar_telefone("home_phone")

    def clean_work_phone(self):
        return self._limpar_telefone("work_phone")

    def clean_birth_date(self):
        date = self.cleaned_data.get("birth_date")
        if date and date > datetime.date.today():
            raise forms.ValidationError(_("A data de nascimento não pode estar no futuro."))
        return date

    def clean(self):
        dados = super().clean()
        kind = dados.get("kind")
        # Checked here because it depends on the person type; a type without a document in
        # this country (an individual in the United States) keeps none.
        do_tipo = (
            self.documentos.empresa if kind == Patient.Tipo.JURIDICA else self.documentos.paciente
        )
        document = ""
        if do_tipo is not None:
            try:
                document = identification.limpar(dados.get("tax_id", ""), [do_tipo], do_tipo.sigla)
            except ValidationError as erro:
                self.add_error("tax_id", erro)
        if "tax_id" in dados:
            dados["tax_id"] = document

        if document:
            # The clinic is not a form field, so the unique constraint is checked here.
            outro = Patient.objects.filter(tax_id=document).exclude(pk=self.instance.pk).first()
            if outro is not None and outro.archived:
                self.add_error(
                    "tax_id",
                    _(
                        "Este documento é de um paciente arquivado. Peça ao administrador "
                        "da clínica para restaurá-lo."
                    ),
                )
            elif outro is not None:
                self.add_error(
                    "tax_id", _("Já existe um paciente com este documento nesta clínica.")
                )

        # Fields that only make sense for one person type are cleared for the other.
        if kind == Patient.Tipo.JURIDICA:
            for campo in ["rg", "sex", "marital_status", "occupation", "guardian"]:
                dados[campo] = None if campo == "marital_status" else ""
            dados["birth_date"] = None
        else:
            dados["legal_name"] = ""
            dados["state_registration"] = ""

        city, state = dados.get("city"), dados.get("state")
        if city is not None and city.state_id != getattr(state, "pk", None):
            self.add_error("city", _("A cidade não pertence à UF escolhida."))
        return dados


class PessoaRelacionadaForm(FormularioBootstrap, forms.ModelForm):
    """A relative or contact (decision 101): another patient of the clinic, or a name."""

    phone = _campo_texto(_("Telefone"), 16, inputmode="tel")

    class Meta:
        model = RelatedPerson
        fields = ["relationship", "other_patient", "name", "phone", "note"]
        widgets = {"other_patient": forms.HiddenInput}
        help_texts = {"name": _("Só para quem não é paciente da clínica.")}

    def __init__(self, *args, patient, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.patient = patient
        if self.instance.clinic_id is None:
            self.instance.clinic_id = patient.clinic_id
        self.fields["other_patient"].queryset = Patient.objects.exclude(pk=patient.pk)

    def clean_phone(self):
        return normalizar_telefone(self.cleaned_data.get("phone"))

    def clean(self):
        dados = super().clean()
        outro, name = dados.get("other_patient"), dados.get("name", "").strip()
        if outro and name:
            self.add_error("name", _("Escolha um paciente ou digite um nome, não os dois."))
        elif not outro and not name:
            self.add_error("name", _("Escolha um paciente da clínica ou digite o nome."))
        dados["name"] = name
        if (
            outro
            and RelatedPerson.objects.filter(
                patient=self.instance.patient,
                other_patient=outro,
                relationship=dados.get("relationship"),
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error("other_patient", _("Este vínculo já está cadastrado."))
        return dados
