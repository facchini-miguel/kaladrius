from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import BootstrapForm
from apps.core.validators import normalize_phone

from . import insurance
from .models import HealthPlan, MemberCard


class HealthPlanForm(BootstrapForm, forms.ModelForm):
    # Typed with punctuation, stored without it (ANS: the 6 digits). Only in the countries
    # whose insurers have a registry (decision 125).
    registration = forms.CharField(max_length=30, required=False)
    phone = forms.CharField(
        label=_("Telefone"),
        max_length=16,
        required=False,
        widget=forms.TextInput({"inputmode": "tel"}),
    )

    class Meta:
        model = HealthPlan
        fields = ["name", "registration", "phone", "notes", "active"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinic_id is None:
            self.instance.clinic = clinic
        for_country = insurance.for_country(clinic.country)
        if for_country.tipos:
            self.fields["name"].help_text = _("Por exemplo: %(tipos)s.") % {
                "tipos": for_country.tipos
            }
        self.registration = for_country.registration
        if self.registration is None:
            del self.fields["registration"]
        else:
            self.fields["registration"].label = insurance.registration_label(clinic.country)
            if self.registration.example:
                self.fields["registration"].widget.attrs["placeholder"] = self.registration.example

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if HealthPlan.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um convênio com este nome."))
        return name

    def clean_registration(self):
        registration = self.registration.clean_value(self.cleaned_data.get("registration"))
        if len(registration) > 20:
            raise forms.ValidationError(_("Use no máximo 20 caracteres."))
        return registration

    def clean_phone(self):
        return normalize_phone(self.cleaned_data.get("phone"))


class MemberCardForm(BootstrapForm, forms.ModelForm):
    class Meta:
        model = MemberCard
        fields = [
            "health_plan",
            "plan",
            "number",
            "group",
            "member_code",
            "valid_until",
            "holder",
            "active",
        ]
        widgets = {"valid_until": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, patient, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.patient = patient
        if self.instance.clinic_id is None:
            self.instance.clinic_id = patient.clinic_id
        # The card's fields and their local names in the clinic's country (decision 125).
        for_country = insurance.for_country(patient.clinic.country)
        self.fields["number"].label = insurance.with_local_name(
            _("Número da carteirinha"), for_country.number
        )
        for field, local, label in (
            ("group", for_country.group, _("Número do grupo")),
            ("member_code", for_country.member_code, _("Código do beneficiário")),
        ):
            if local or getattr(self.instance, field):
                self.fields[field].label = insurance.with_local_name(label, local)
            else:
                del self.fields[field]
        # Active plans, plus the card's own plan when it was deactivated later.
        self.fields["health_plan"].queryset = HealthPlan.objects.filter(active=True) | (
            HealthPlan.objects.filter(pk=self.instance.health_plan_id)
        )

    def clean_number(self):
        return self.cleaned_data["number"].strip()

    def clean(self):
        data = super().clean()
        health_plan, number = data.get("health_plan"), data.get("number")
        if (
            health_plan
            and number
            and MemberCard.objects.filter(health_plan=health_plan, number=number)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error("number", _("Esta carteirinha já está cadastrada neste convênio."))
        return data
