import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from apps.core import countries, identification
from apps.core.forms import BootstrapForm, document_by_kind, document_field
from apps.core.validators import normalize_phone
from apps.reference_data.models import City, State

from .models import Patient, RelatedPerson


class StateField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.abbreviation} - {obj.name}"


class CityField(forms.ModelChoiceField):
    """City select labeled by name only (the state is chosen in the field beside it)."""

    def label_from_instance(self, obj):
        return obj.name


def _text_field(label, max_length, **attrs):
    """Optional text field that accepts punctuation; the value is normalized in clean_*()."""
    return forms.CharField(
        label=label,
        max_length=max_length,
        required=False,
        widget=forms.TextInput(attrs=attrs),
    )


class PatientForm(BootstrapForm, forms.ModelForm):
    state = StateField(queryset=State.objects.all(), required=False, label=_("UF"))
    city = CityField(queryset=City.objects.none(), required=False, label=_("Cidade"))
    # The country's document (decision 121), typed with punctuation, stored compact.
    tax_id = document_field()
    postal_code = _text_field(_("CEP"), 10)
    mobile_phone = _text_field(_("Celular"), 16, inputmode="tel")
    whatsapp = _text_field(_("WhatsApp"), 16, inputmode="tel")
    home_phone = _text_field(_("Telefone residencial"), 16, inputmode="tel")
    work_phone = _text_field(_("Telefone comercial"), 16, inputmode="tel")

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
    BRAZIL_ONLY = ["state_registration", "rg", "state", "city"]
    OUTSIDE_BRAZIL = ["state_name", "city_name"]

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinic_id is None:
            self.instance.clinic = clinic
        self.country = countries.clinic_country(clinic)
        self.fields["postal_code"].label = countries.postal_code_label(self.country)
        self.documentos = identification.for_country(self.country)
        document_by_kind(
            self.fields["tax_id"],
            self.documentos.paciente,
            self.documentos.empresa,
            self["kind"].value(),
        )
        for field in self.OUTSIDE_BRAZIL if self.country == "BR" else self.BRAZIL_ONLY:
            del self.fields[field]
        if self.country != "BR":
            return
        self.fields["postal_code"].widget.attrs["inputmode"] = "numeric"

        # Chained selects: the city list depends on the chosen state (HTMX).
        self.fields["state"].widget.attrs.update(
            {
                "hx-get": reverse("reference_data:city_options"),
                "hx-target": "#id_city",
                "hx-trigger": "change",
            }
        )
        # Known neighborhoods and streets of the chosen city as suggestions (decision 100);
        # anything else can still be typed.
        self.fields["city"].widget.attrs.update(
            {
                "hx-get": reverse("reference_data:address_suggestions"),
                "hx-target": "#address-suggestions",
                "hx-trigger": "load, change",
            }
        )
        for field, patient_list in (
            ("neighborhood", "suggested-neighborhoods"),
            ("street", "suggested-streets"),
        ):
            self.fields[field].widget.attrs.update({"list": patient_list, "autocomplete": "off"})
        state_id = (
            self.data.get(self.add_prefix("state")) if self.is_bound else self.instance.state_id
        )
        self.fields["city"].queryset = (
            City.objects.filter(state_id=int(state_id))
            if str(state_id or "").isdecimal()
            else City.objects.none()
        )

    def clean_postal_code(self):
        return countries.normalize_postal_code(self.cleaned_data.get("postal_code"), self.country)

    def _clean_phone(self, name):
        return normalize_phone(self.cleaned_data.get(name), self.country)

    def clean_mobile_phone(self):
        return self._clean_phone("mobile_phone")

    def clean_whatsapp(self):
        return self._clean_phone("whatsapp")

    def clean_home_phone(self):
        return self._clean_phone("home_phone")

    def clean_work_phone(self):
        return self._clean_phone("work_phone")

    def clean_birth_date(self):
        date = self.cleaned_data.get("birth_date")
        if date and date > datetime.date.today():
            raise forms.ValidationError(_("A data de nascimento não pode estar no futuro."))
        return date

    def clean(self):
        data = super().clean()
        kind = data.get("kind")
        # Checked here because it depends on the person type; a type without a document in
        # this country (an individual in the United States) keeps none.
        do_tipo = (
            self.documentos.empresa if kind == Patient.Kind.COMPANY else self.documentos.paciente
        )
        document = ""
        if do_tipo is not None:
            try:
                document = identification.clean_value(
                    data.get("tax_id", ""), [do_tipo], do_tipo.abbreviation
                )
            except ValidationError as error:
                self.add_error("tax_id", error)
        if "tax_id" in data:
            data["tax_id"] = document

        if document:
            # The clinic is not a form field, so the unique constraint is checked here.
            other = Patient.objects.filter(tax_id=document).exclude(pk=self.instance.pk).first()
            if other is not None and other.archived:
                self.add_error(
                    "tax_id",
                    _(
                        "Este documento é de um paciente arquivado. Peça ao administrador "
                        "da clínica para restaurá-lo."
                    ),
                )
            elif other is not None:
                self.add_error(
                    "tax_id", _("Já existe um paciente com este documento nesta clínica.")
                )

        # Fields that only make sense for one person type are cleared for the other.
        if kind == Patient.Kind.COMPANY:
            for field in ["rg", "sex", "marital_status", "occupation", "guardian"]:
                data[field] = None if field == "marital_status" else ""
            data["birth_date"] = None
        else:
            data["legal_name"] = ""
            data["state_registration"] = ""

        city, state = data.get("city"), data.get("state")
        if city is not None and city.state_id != getattr(state, "pk", None):
            self.add_error("city", _("A cidade não pertence à UF escolhida."))
        return data


class RelatedPersonForm(BootstrapForm, forms.ModelForm):
    """A relative or contact (decision 101): another patient of the clinic, or a name."""

    phone = _text_field(_("Telefone"), 16, inputmode="tel")

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
        return normalize_phone(self.cleaned_data.get("phone"))

    def clean(self):
        data = super().clean()
        other, name = data.get("other_patient"), data.get("name", "").strip()
        if other and name:
            self.add_error("name", _("Escolha um paciente ou digite um nome, não os dois."))
        elif not other and not name:
            self.add_error("name", _("Escolha um paciente da clínica ou digite o nome."))
        data["name"] = name
        if (
            other
            and RelatedPerson.objects.filter(
                patient=self.instance.patient,
                other_patient=other,
                relationship=data.get("relationship"),
            )
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error("other_patient", _("Este vínculo já está cadastrado."))
        return data
