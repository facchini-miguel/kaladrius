from django import forms

from apps.core.forms import FormularioBootstrap

from .models import CAMPOS_DA_ANAMNESE, Adendo, Atendimento


class AtendimentoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Atendimento
        fields = ["data", *CAMPOS_DA_ANAMNESE]
        widgets = {
            "data": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            **{campo: forms.Textarea(attrs={"rows": 4}) for campo in CAMPOS_DA_ANAMNESE},
        }


class AdendoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Adendo
        fields = ["texto"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 3})}
