from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import FormularioBootstrap

from .models import CAMPOS_DA_ANAMNESE, Adendo, Atendimento, Atestado, Receita


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


class AtestadoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Atestado
        fields = ["tipo", "data", "hora_inicio", "hora_fim", "dias", "observacao"]
        widgets = {
            "tipo": forms.RadioSelect,
            "data": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "observacao": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        dados = super().clean()
        if dados.get("tipo") == Atestado.Tipo.AFASTAMENTO:
            if not dados.get("dias"):
                self.add_error("dias", _("Informe quantos dias de afastamento."))
        else:
            dados["dias"] = None
        inicio, fim = dados.get("hora_inicio"), dados.get("hora_fim")
        if inicio and fim and fim <= inicio:
            self.add_error("hora_fim", _("O horário final precisa ser depois do inicial."))
        return dados


class ReceitaForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Receita
        fields = ["prescricao"]
        widgets = {"prescricao": forms.Textarea(attrs={"rows": 8})}
