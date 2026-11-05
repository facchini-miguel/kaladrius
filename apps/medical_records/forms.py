from django import forms
from django.utils.translation import gettext_lazy as _

from apps.core.forms import BootstrapForm

from .models import CAMPOS_DA_ANAMNESE, Addendum, Certificate, ExamRequest, Prescription, Visit


class AtendimentoForm(BootstrapForm, forms.ModelForm):
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
            **{field: forms.Textarea(attrs={"rows": 4}) for field in CAMPOS_DA_ANAMNESE},
        }


class AdendoForm(BootstrapForm, forms.ModelForm):
    class Meta:
        model = Addendum
        fields = ["text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3})}


class AtestadoForm(BootstrapForm, forms.ModelForm):
    class Meta:
        model = Certificate
        fields = ["kind", "date", "start_time", "end_time", "days", "note"]
        widgets = {
            "kind": forms.RadioSelect,
            "date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "start_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "end_time": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        data = super().clean()
        if data.get("kind") == Certificate.Tipo.AFASTAMENTO:
            if not data.get("days"):
                self.add_error("days", _("Informe quantos dias de afastamento."))
        else:
            data["days"] = None
        start, end = data.get("start_time"), data.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", _("O horário final precisa ser depois do inicial."))
        return data


class ReceitaForm(BootstrapForm, forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ["medications"]
        widgets = {"medications": forms.Textarea(attrs={"rows": 8})}


class PedidoDeExamesForm(BootstrapForm, forms.ModelForm):
    class Meta:
        model = ExamRequest
        fields = ["exams", "indication"]
        widgets = {
            "exams": forms.Textarea(attrs={"rows": 8}),
            "indication": forms.Textarea(attrs={"rows": 2}),
        }


# Attachments (decision 083): checked by their first bytes, not by the name or the type the
# browser sends, so nothing else (HTML, scripts) is ever stored or served back.
TAMANHO_MAXIMO_DO_ANEXO = 10 * 1024 * 1024
ASSINATURAS = [
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]


class AnexoForm(BootstrapForm, forms.Form):
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
