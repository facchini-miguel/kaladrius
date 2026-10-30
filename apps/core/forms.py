import datetime

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from .models import Clinica, ModuloClinico, ModuloDaClinica
from .modulos import configurar, iniciais
from .validadores import cnpj_valido, cpf_valido, normalizar_cnpj


class FormularioBootstrap:
    """Mixin that adds Bootstrap 5 classes to every widget of a form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if isinstance(campo, forms.ModelChoiceField) and campo.empty_label is not None:
                # Django 6.1's "- Select an option -" has no Portuguese translation yet.
                campo.empty_label = "—"
            widget = campo.widget
            if isinstance(
                widget, forms.CheckboxInput | forms.RadioSelect | forms.CheckboxSelectMultiple
            ):
                classe = "form-check-input"
            elif isinstance(widget, forms.Select):
                classe = "form-select"
            elif getattr(widget, "input_type", None) == "color":
                classe = "form-control form-control-color"
            else:
                classe = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {classe}".strip()

    def full_clean(self):
        super().full_clean()
        # Mark invalid fields so Bootstrap shows them in red.
        for nome in self.errors:
            if nome in self.fields:
                widget = self.fields[nome].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


class TrocaSenhaForm(FormularioBootstrap, PasswordChangeForm):
    """The user's own password change, with Bootstrap styling."""


class ModulosClinicosForm(FormularioBootstrap, forms.ModelForm):
    modulos = forms.MultipleChoiceField(
        label=_("Módulos clínicos"),
        choices=ModuloClinico.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_(
            "Escolha uma área, ambas ou nenhuma. Agenda, pacientes, prontuário comum e "
            "financeiro continuam disponíveis. Desativar não apaga o histórico."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["modulos"] = (
            list(
                ModuloDaClinica.todos.filter(clinica=self.instance, ativo=True).values_list(
                    "codigo", flat=True
                )
            )
            if self.instance.pk
            else list(iniciais(self.instance.area))
        )

    def _save_m2m(self):
        super()._save_m2m()
        configurar(self.instance, self.cleaned_data["modulos"])

    @transaction.atomic
    def save(self, commit=True):
        return super().save(commit=commit)


class ClinicaForm(ModulosClinicosForm):
    """Clinic details and schedule settings, changed by the clinic administrator."""

    # Typed with punctuation (up to 18 characters), stored as 11 or 14.
    documento = forms.CharField(label=_("CPF/CNPJ"), max_length=18, required=False)

    class Meta:
        model = Clinica
        fields = ["nome", "area", "documento", "email", "telefone", "endereco"] + [
            "agenda_inicio",
            "agenda_fim",
            "agenda_intervalo",
        ]
        widgets = {
            "agenda_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "agenda_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }
        help_texts = {
            "agenda_intervalo": _("Os agendamentos começam e terminam em múltiplos deste tempo."),
        }

    def clean_documento(self):
        documento = normalizar_cnpj(self.cleaned_data.get("documento", ""))
        if documento and not (
            cpf_valido(documento) if len(documento) == 11 else cnpj_valido(documento)
        ):
            raise forms.ValidationError(_("CPF/CNPJ inválido."))
        return documento

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get("agenda_inicio"), dados.get("agenda_fim")
        intervalo = dados.get("agenda_intervalo")
        if None in (inicio, fim, intervalo):
            return dados
        if inicio >= fim:
            self.add_error("agenda_fim", _("O fim da agenda deve ser depois do início."))
            return dados
        problema = self._agendamento_fora(inicio, fim, intervalo)
        if problema is not None:
            raise forms.ValidationError(
                _(
                    "O agendamento de %(momento)s ficaria fora do novo horário ou do novo "
                    "intervalo. Ajuste os agendamentos futuros antes de mudar a agenda."
                )
                % {"momento": date_format(problema, "SHORT_DATETIME_FORMAT")}
            )
        return dados

    def _agendamento_fora(self, inicio, fim, intervalo):
        """Start of the first future appointment the new settings would leave out, if any.

        Past appointments are not checked: the history may have other hours.
        """
        from apps.agenda.models import Agendamento

        def minutos(hora):
            return hora.hour * 60 + hora.minute

        base = minutos(inicio)
        if self.instance.pk is None:
            return None
        # Django Admin runs without the request's clinic isolation. Validate only the
        # clinic being edited, including when this form is used outside a request.
        futuros = Agendamento.todos.filter(clinica=self.instance, fim__gt=timezone.now()).order_by(
            "inicio"
        )
        for comeca, termina in futuros.values_list("inicio", "fim"):
            comeca, termina = timezone.localtime(comeca), timezone.localtime(termina)
            horas = (comeca.time(), termina.time())
            fora = comeca.time() < inicio or (
                termina.time() > fim and termina.time() != datetime.time(0)
            )
            desalinhado = any((minutos(h) - base) % intervalo or h.second for h in horas)
            if fora or desalinhado:
                return comeca
        return None


class NovaClinicaForm(ModulosClinicosForm):
    """The installation's clinic, registered on the first access (decision 069). The
    schedule and the rest are set later in the clinic settings."""

    class Meta:
        model = Clinica
        fields = ["nome", "area", "documento", "email", "telefone", "endereco"]


class ClinicaAdminForm(ClinicaForm):
    class Meta(ClinicaForm.Meta):
        fields = [*ClinicaForm.Meta.fields, "ativa"]
