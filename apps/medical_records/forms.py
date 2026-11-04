from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import FormularioBootstrap

from .models import CAMPOS_DA_ANAMNESE, Addendum, Certificate, ExamRequest, Prescription, Visit


class AtendimentoForm(FormularioBootstrap, forms.ModelForm):
    """With `profissionais`, a new visit also asks on behalf of which practitioner it is
    written (the system administrator, decision 087)."""

    def __init__(self, *args, profissionais=None, **kwargs):
        if profissionais is not None:
            # Before the mixin's __init__, so it gets the Bootstrap classes too.
            self.base_fields = {
                "practitioner": forms.ModelChoiceField(
                    queryset=profissionais, label=_("Profissional")
                ),
                **self.base_fields,
            }
        super().__init__(*args, **kwargs)

    class Meta:
        model = Visit
        fields = ["date", *CAMPOS_DA_ANAMNESE]
        widgets = {
            "date": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            **{campo: forms.Textarea(attrs={"rows": 4}) for campo in CAMPOS_DA_ANAMNESE},
        }


class AdendoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Addendum
        fields = ["texto"]
        widgets = {"texto": forms.Textarea(attrs={"rows": 3})}


class AtestadoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Certificate
        fields = ["kind", "date", "hora_inicio", "hora_fim", "dias", "note"]
        widgets = {
            "kind": forms.RadioSelect,
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "hora_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        dados = super().clean()
        if dados.get("kind") == Certificate.Tipo.AFASTAMENTO:
            if not dados.get("dias"):
                self.add_error("dias", _("Informe quantos dias de afastamento."))
        else:
            dados["dias"] = None
        start, end = dados.get("hora_inicio"), dados.get("hora_fim")
        if start and end and end <= start:
            self.add_error("hora_fim", _("O horário final precisa ser depois do inicial."))
        return dados


class ReceitaForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ["prescricao"]
        widgets = {"prescricao": forms.Textarea(attrs={"rows": 8})}


class PedidoDeExamesForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = ExamRequest
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
    file = forms.FileField(label=_("Arquivo"), help_text=_("PDF, JPG ou PNG, até 10 MB."))
    description = forms.CharField(
        label=_("Descrição"),
        max_length=200,
        required=False,
        help_text=_("Por exemplo: hemograma de março."),
    )

    def clean_file(self):
        file = self.cleaned_data["file"]
        if file.size > TAMANHO_MAXIMO_DO_ANEXO:
            raise forms.ValidationError(_("O arquivo passa de 10 MB."))
        start = file.read(8)
        file.seek(0)
        kind = next(
            (kind for assinatura, kind in ASSINATURAS if start.startswith(assinatura)), None
        )
        if kind is None:
            raise forms.ValidationError(_("Envie um arquivo PDF, JPG ou PNG."))
        file.tipo_conferido = kind
        return file
