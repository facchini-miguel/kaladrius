from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import FormularioBootstrap
from apps.patients.models import Patient

from .models import Recall


class RechamadaForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Recall
        fields = ["patient", "date", "description", "concluida"]
        widgets = {
            "patient": forms.HiddenInput,
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinic_id is None:
            self.instance.clinic = clinic
        self.fields["patient"].queryset = Patient.objects.all()
        self.fields["patient"].error_messages["required"] = _("Escolha o paciente.")
