from django import forms

from apps.core.forms import FormularioBootstrap

from .models import TipoAtendimento


class TipoAtendimentoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = TipoAtendimento
        fields = ["nome", "cor", "ativo"]
        widgets = {"cor": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinica_id is None:
            self.instance.clinica = clinica

    def clean_nome(self):
        # The clinic is not a form field, so the unique constraint must be checked here.
        nome = self.cleaned_data["nome"].strip()
        repetido = TipoAtendimento.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise forms.ValidationError("Já existe um tipo de atendimento com este nome.")
        return nome
