from django import forms

from apps.core.forms import FormularioBootstrap
from apps.pacientes.models import Paciente

from .models import Rechamada


class RechamadaForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Rechamada
        fields = ["paciente", "data", "descricao", "concluida"]
        widgets = {
            "paciente": forms.HiddenInput,
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinica_id is None:
            self.instance.clinica = clinica
        self.fields["paciente"].queryset = Paciente.objects.all()
        self.fields["paciente"].error_messages["required"] = "Escolha o paciente."
