from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import FormularioBootstrap

from .models import CAMPOS_DA_ANAMNESE, Adendo, Atendimento, Atestado, PedidoDeExames, Receita


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


class PedidoDeExamesForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = PedidoDeExames
        fields = ["exames", "indicacao"]
        widgets = {
            "exames": forms.Textarea(attrs={"rows": 8}),
            "indicacao": forms.Textarea(attrs={"rows": 2}),
        }


# Attachments (decision 083): checked by their first bytes, not by the name or the type the
# browser sends, so nothing else (HTML, scripts) is ever stored or served back.
TAMANHO_MAXIMO_DO_ANEXO = 10 * 1024 * 1024
ASSINATURAS = [
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]


class AnexoForm(FormularioBootstrap, forms.Form):
    arquivo = forms.FileField(label=_("Arquivo"), help_text=_("PDF, JPG ou PNG, até 10 MB."))
    descricao = forms.CharField(
        label=_("Descrição"),
        max_length=200,
        required=False,
        help_text=_("Por exemplo: hemograma de março."),
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if arquivo.size > TAMANHO_MAXIMO_DO_ANEXO:
            raise forms.ValidationError(_("O arquivo passa de 10 MB."))
        inicio = arquivo.read(8)
        arquivo.seek(0)
        tipo = next(
            (tipo for assinatura, tipo in ASSINATURAS if inicio.startswith(assinatura)), None
        )
        if tipo is None:
            raise forms.ValidationError(_("Envie um arquivo PDF, JPG ou PNG."))
        arquivo.tipo_conferido = tipo
        return arquivo
