from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import FormularioBootstrap
from apps.core.validadores import normalizar_telefone

from . import seguros
from .models import Carteirinha, Convenio


class ConvenioForm(FormularioBootstrap, forms.ModelForm):
    # Typed with punctuation, stored without it (ANS: the 6 digits). Only in the countries
    # whose insurers have a registry (decision 125).
    registro = forms.CharField(max_length=30, required=False)
    telefone = forms.CharField(
        label=_("Telefone"),
        max_length=16,
        required=False,
        widget=forms.TextInput({"inputmode": "tel"}),
    )

    class Meta:
        model = Convenio
        fields = ["nome", "registro", "telefone", "observacoes", "ativo"]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinica_id is None:
            self.instance.clinica = clinica
        do_pais = seguros.do_pais(clinica.pais)
        if do_pais.tipos:
            self.fields["nome"].help_text = _("Por exemplo: %(tipos)s.") % {"tipos": do_pais.tipos}
        self.registro = do_pais.registro
        if self.registro is None:
            del self.fields["registro"]
        else:
            self.fields["registro"].label = seguros.rotulo_do_registro(clinica.pais)
            if self.registro.exemplo:
                self.fields["registro"].widget.attrs["placeholder"] = self.registro.exemplo

    def clean_nome(self):
        nome = self.cleaned_data["nome"].strip()
        if Convenio.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(_("Já existe um convênio com este nome."))
        return nome

    def clean_registro(self):
        registro = self.registro.limpar(self.cleaned_data.get("registro"))
        if len(registro) > 20:
            raise forms.ValidationError(_("Use no máximo 20 caracteres."))
        return registro

    def clean_telefone(self):
        return normalizar_telefone(self.cleaned_data.get("telefone"))


class CarteirinhaForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Carteirinha
        fields = [
            "convenio",
            "plano",
            "numero",
            "grupo",
            "beneficiario",
            "validade",
            "titular",
            "ativa",
        ]
        widgets = {"validade": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, paciente, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.paciente = paciente
        if self.instance.clinica_id is None:
            self.instance.clinica_id = paciente.clinica_id
        # The card's fields and their local names in the clinic's country (decision 125).
        do_pais = seguros.do_pais(paciente.clinica.pais)
        self.fields["numero"].label = seguros.com_nome_local(
            _("Número da carteirinha"), do_pais.numero
        )
        for campo, local, rotulo in (
            ("grupo", do_pais.grupo, _("Número do grupo")),
            ("beneficiario", do_pais.beneficiario, _("Código do beneficiário")),
        ):
            if local or getattr(self.instance, campo):
                self.fields[campo].label = seguros.com_nome_local(rotulo, local)
            else:
                del self.fields[campo]
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
