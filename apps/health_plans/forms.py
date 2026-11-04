from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import FormularioBootstrap
from apps.core.validators import normalizar_telefone

from . import insurance
from .models import HealthPlan, MemberCard


class ConvenioForm(FormularioBootstrap, forms.ModelForm):
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
        do_pais = insurance.do_pais(clinic.pais)
        if do_pais.tipos:
            self.fields["name"].help_text = _("Por exemplo: %(tipos)s.") % {"tipos": do_pais.tipos}
        self.registration = do_pais.registration
        if self.registration is None:
            del self.fields["registration"]
        else:
            self.fields["registration"].label = insurance.rotulo_do_registro(clinic.pais)
            if self.registration.exemplo:
                self.fields["registration"].widget.attrs["placeholder"] = self.registration.exemplo

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if HealthPlan.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um convênio com este nome."))
        return name

    def clean_registration(self):
        registration = self.registration.limpar(self.cleaned_data.get("registration"))
        if len(registration) > 20:
            raise forms.ValidationError(_("Use no máximo 20 caracteres."))
        return registration

    def clean_phone(self):
        return normalizar_telefone(self.cleaned_data.get("phone"))


class CarteirinhaForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = MemberCard
        fields = [
            "convenio",
            "plano",
            "number",
            "group",
            "beneficiario",
            "valid_until",
            "titular",
            "active",
        ]
        widgets = {"valid_until": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, patient, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.patient = patient
        if self.instance.clinic_id is None:
            self.instance.clinic_id = patient.clinic_id
        # The card's fields and their local names in the clinic's country (decision 125).
        do_pais = insurance.do_pais(patient.clinic.pais)
        self.fields["number"].label = insurance.com_nome_local(
            _("Número da carteirinha"), do_pais.number
        )
        for campo, local, rotulo in (
            ("group", do_pais.group, _("Número do grupo")),
            ("beneficiario", do_pais.beneficiario, _("Código do beneficiário")),
        ):
            if local or getattr(self.instance, campo):
                self.fields[campo].label = insurance.com_nome_local(rotulo, local)
            else:
                del self.fields[campo]
        # Active plans, plus the card's own plan when it was deactivated later.
        self.fields["convenio"].queryset = HealthPlan.objects.filter(active=True) | (
            HealthPlan.objects.filter(pk=self.instance.convenio_id)
        )

    def clean_number(self):
        return self.cleaned_data["number"].strip()

    def clean(self):
        dados = super().clean()
        convenio, number = dados.get("convenio"), dados.get("number")
        if (
            convenio
            and number
            and MemberCard.objects.filter(convenio=convenio, number=number)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error("number", _("Esta carteirinha já está cadastrada neste convênio."))
        return dados
