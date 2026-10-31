from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import FormularioBootstrap
from apps.core.validadores import normalizar_telefone, somente_digitos

from .models import Carteirinha, Convenio


class ConvenioForm(FormularioBootstrap, forms.ModelForm):
    # Typed with punctuation, stored as the 6 digits.
    registro_ans = forms.CharField(
        label=_("Registro na ANS"),
        max_length=10,
        required=False,
        help_text=Convenio._meta.get_field("registro_ans").help_text,
    )
    telefone = forms.CharField(
        label=_("Telefone"),
        max_length=16,
        required=False,
        widget=forms.TextInput({"inputmode": "tel"}),
    )

    class Meta:
        model = Convenio
        fields = ["nome", "registro_ans", "telefone", "observacoes", "ativo"]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinica_id is None:
            self.instance.clinica = clinica

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        if Convenio.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um convênio com este nome."))
        return nome

    def clean_registro_ans(self):
        registro = somente_digitos(self.cleaned_data.get("registro_ans"))
        if registro and len(registro) != 6:
            raise forms.ValidationError(_("O registro na ANS tem 6 dígitos."))
        return registro

    def clean_telefone(self):
        return normalizar_telefone(self.cleaned_data.get("telefone"))


class CarteirinhaForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Carteirinha
        fields = ["convenio", "plano", "numero", "validade", "titular", "ativa"]
        widgets = {"validade": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, paciente, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.paciente = paciente
        if self.instance.clinica_id is None:
            self.instance.clinica_id = paciente.clinica_id
        # Active plans, plus the card's own plan when it was deactivated later.
        self.fields["convenio"].queryset = Convenio.objects.filter(ativo=True) | (
            Convenio.objects.filter(pk=self.instance.convenio_id)
        )

    def clean_numero(self):
        return self.cleaned_data["numero"].strip()

    def clean(self):
        dados = super().clean()
        convenio, numero = dados.get("convenio"), dados.get("numero")
        if (
            convenio
            and numero
            and Carteirinha.objects.filter(convenio=convenio, numero=numero)
            .exclude(pk=self.instance.pk)
            .exists()
        ):
            self.add_error("numero", _("Esta carteirinha já está cadastrada neste convênio."))
        return dados
