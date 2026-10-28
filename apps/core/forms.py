import datetime

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _

from .models import Clinica
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
            if isinstance(widget, forms.CheckboxInput | forms.RadioSelect):
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


class ClinicaForm(FormularioBootstrap, forms.ModelForm):
    """Clinic details and schedule settings, changed by the clinic administrator."""

    # Typed with punctuation (up to 18 characters), stored as 11 or 14.
    documento = forms.CharField(label=_("CPF/CNPJ"), max_length=18, required=False)

    class Meta:
        model = Clinica
        fields = ["nome", "documento", "email", "telefone", "endereco"] + [
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
        futuros = Agendamento.objects.filter(fim__gt=timezone.now()).order_by("inicio")
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


class NovaClinicaForm(FormularioBootstrap, forms.ModelForm):
    """The installation's clinic, registered on the first access (decision 069). The
    schedule and the rest are set later in the clinic settings."""

    class Meta:
        model = Clinica
        fields = ["nome", "documento", "email", "telefone", "endereco"]
