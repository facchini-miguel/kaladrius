import datetime
import re

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format, get_format
from django.utils.translation import gettext_lazy as _

from . import countries, currencies, identification
from .models import GENERAL_MODULES, SPECIALTIES, Clinic, ClinicModule, ModuleCode
from .modules import configure, initial, missing


def _options(group):
    return [(value, name) for value, name in ModuleCode.choices if value in group]


class LocalizedDecimalField(forms.DecimalField):
    """A number typed the way people write it: "1.500,00", "R$ 1.500,00", "€ 1.500" or "1500,00" in
    Portuguese and Spanish ("1,500.00" in English). Django's own field refused the
    thousands separator ("Informe um número."), and "1.500" read as one and a half.
    """

    def to_python(self, value):
        if isinstance(value, str):
            value = self._without_thousands(value)
        return super().to_python(value)

    @staticmethod
    def _without_thousands(text):
        # The currency symbols of apps/core/currencies.py (R$, US$, €, $U, S/, ₲...) and spaces;
        # anything else stays, so "abc" is still refused.
        for symbol in currencies.SYMBOLS:
            text = text.replace(symbol, "")
        text = re.sub(r"\s", "", text)
        decimal = get_format("DECIMAL_SEPARATOR")
        milhar = "." if decimal == "," else ","
        grupos = rf"-?\d{{1,3}}(\{milhar}\d{{3}})+"
        if decimal in text or re.fullmatch(grupos, text):
            # "1.500,00" and "1.500": the dots group thousands.
            return text.replace(milhar, "")
        # "1500.00": a lone point is taken as the decimal mark, whatever the language.
        return text if decimal == "," else text.replace(milhar, decimal)


class BootstrapForm:
    """Mixin that adds Bootstrap 5 classes to every widget of a form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if type(field) is forms.DecimalField:
                field.__class__ = LocalizedDecimalField
            # Django 6.1's "- Select an option -" has no Portuguese translation yet: the
            # blank option of every list becomes a dash, from a table or fixed choices.
            if isinstance(field, forms.ModelChoiceField):
                if field.empty_label is not None:
                    field.empty_label = "—"
            elif isinstance(field, forms.ChoiceField):
                options = list(field.choices)
                if options and options[0][0] in ("", None) and not isinstance(options[0][1], list):
                    field.choices = [("", "—"), *options[1:]]
            widget = field.widget
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
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


def document_field():
    """A document of the clinic's country, typed with or without punctuation (decision 121).
    The form names it and checks it (apps/core/identification.py)."""
    return forms.CharField(
        label=_("Documento"),
        max_length=25,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )


def document_by_kind(field, individuo, empresa, kind):
    """Name and example of a document field that depends on the person type: the document of
    an individual and of a company (either may be None, and then the field is hidden for that
    type). The page switches them when the type changes (static/js/page.js)."""
    current = empresa if kind == "PJ" else individuo
    field.label = (current or individuo or empresa).abbreviation
    field.widget.attrs.update(
        {
            "data-label-pf": individuo.abbreviation if individuo else "",
            "data-label-pj": empresa.abbreviation if empresa else "",
            "data-example-pf": individuo.example if individuo else "",
            "data-example-pj": empresa.example if empresa else "",
            "placeholder": current.example if current else "",
        }
    )


class ChangePasswordForm(BootstrapForm, PasswordChangeForm):
    """The user's own password change, with Bootstrap styling."""


class ClinicModulesForm(BootstrapForm, forms.ModelForm):
    """Specialties and general modules of the clinic (decision 092)."""

    modules = forms.MultipleChoiceField(
        label=_("Especialidades"),
        choices=_options(SPECIALTIES),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_(
            "Só Odontologia, só Medicina ou as duas juntas (ou nenhuma, em outra área da "
            "saúde). Desativar não apaga o histórico."
        ),
    )
    general_modules = forms.MultipleChoiceField(
        label=_("Módulos"),
        choices=_options(GENERAL_MODULES),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_(
            "Comuns às especialidades. Um módulo desligado sai do menu e das telas para toda "
            "a equipe, e nada do que já foi registrado é apagado. Pacientes, profissionais, "
            "equipe e tabelas base estão sempre ligados."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        ligados = set(
            ClinicModule.all_objects.filter(clinic=self.instance, active=True).values_list(
                "code", flat=True
            )
            if self.instance.pk
            else initial(self.instance.area)
        )
        self.initial["modules"] = sorted(ligados & SPECIALTIES)
        self.initial["general_modules"] = sorted(ligados & GENERAL_MODULES)
        # The screen always sends them; a page opened before the update does not, and then
        # the clinic keeps its currency, country and time zone (Brazil's for a new one).
        for field in ("currency", "country", "time_zone", "tooth_numbering"):
            if field in self.fields:
                self.fields[field].required = False
        # The country's tax document, an individual's or a company's (decision 121): "CPF/CNPJ"
        # in Brazil, "EIN" in the United States... of the country chosen now.
        if "document" in self.fields:
            documentos = identification.for_country(self._chosen_country())
            self.documentos_da_clinica = documentos.of_roles("pessoa", "empresa")
            field = self.fields["document"]
            field.label = documentos.label("pessoa", "empresa")
            field.widget.attrs["placeholder"] = " · ".join(
                d.example for d in self.documentos_da_clinica
            )

    def clean_document(self):
        return identification.clean_value(
            self.cleaned_data.get("document", ""),
            self.documentos_da_clinica,
            self.fields["document"].label,
        )

    def _chosen_country(self):
        if self.is_bound and self.data.get(self.add_prefix("country")):
            return self.data[self.add_prefix("country")]
        return self.instance.country or countries.DEFAULT

    def clean_currency(self):
        return self.cleaned_data.get("currency") or self.instance.currency or currencies.DEFAULT

    def clean_country(self):
        return self.cleaned_data.get("country") or self.instance.country or countries.DEFAULT

    def _adjust_to_country(self, data):
        """Time zone and currency of a new country (decision 117): a time zone of another country
        is refused; left as it was, it becomes the new country's first. The currency follows the
        country when it was still the previous country's default and was not changed now."""
        if "country" not in data:
            return
        country = countries.by_code(data["country"])
        fuso = data.get("time_zone")
        if "time_zone" in self.fields and fuso and fuso not in country.fusos:
            if "time_zone" in self.changed_data:
                self.add_error(
                    "time_zone",
                    _("Escolha um fuso horário de %(pais)s.") % {"pais": country.name},
                )
            else:
                data["time_zone"] = country.fusos[0]
        elif not fuso:
            current = self.instance.time_zone
            data["time_zone"] = current if current in country.fusos else country.fusos[0]
        previous = countries.by_code(self.instance.country)
        if (
            "country" in self.changed_data
            and "currency" not in self.changed_data
            and data.get("currency") == previous.currency
        ):
            data["currency"] = country.currency
        # The tooth numbering too (decision 122); a new clinic, without the field, gets its
        # country's.
        if "tooth_numbering" not in self.fields:
            self.instance.tooth_numbering = country.numeracao
        else:
            current = self.instance.tooth_numbering or previous.numeracao
            escolhida = data.get("tooth_numbering") or current
            if "country" in self.changed_data and escolhida == current == previous.numeracao:
                escolhida = country.numeracao
            data["tooth_numbering"] = escolhida

    def _chosen(self):
        return {
            *self.cleaned_data.get("modules", ()),
            *self.cleaned_data.get("general_modules", ()),
        }

    def clean(self):
        data = super().clean()
        self._adjust_to_country(data)
        for modulo, precisa in missing(self._chosen()).items():
            self.add_error(
                "general_modules",
                _("%(modulo)s precisa de: %(precisa)s.")
                % {
                    "modulo": ModuleCode(modulo).label,
                    "precisa": ", ".join(str(ModuleCode(p).label) for p in sorted(precisa)),
                },
            )
        return data

    def _save_m2m(self):
        super()._save_m2m()
        configure(self.instance, self._chosen())

    @transaction.atomic
    def save(self, commit=True):
        return super().save(commit=commit)


class ClinicForm(ClinicModulesForm):
    """Clinic details and schedule settings, changed by the clinic administrator."""

    document = document_field()

    class Meta:
        model = Clinic
        fields = [
            "name",
            "area",
            "country",
            "document",
            "email",
            "phone",
            "address",
            "currency",
            "time_zone",
            "tooth_numbering",
        ] + [
            "schedule_start",
            "schedule_end",
            "schedule_interval",
            "require_two_factor",
        ]
        widgets = {
            "schedule_start": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "schedule_end": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }
        help_texts = {
            "schedule_interval": _("Os agendamentos começam e terminam em múltiplos deste tempo."),
        }

    def clean(self):
        data = super().clean()
        start, end = data.get("schedule_start"), data.get("schedule_end")
        intervalo = data.get("schedule_interval")
        if None in (start, end, intervalo):
            return data
        if start >= end:
            self.add_error("schedule_end", _("O fim da agenda deve ser depois do início."))
            return data
        problema = self._appointment_outside(start, end, intervalo)
        if problema is not None:
            raise forms.ValidationError(
                _(
                    "O agendamento de %(momento)s ficaria fora do novo horário ou do novo "
                    "intervalo. Ajuste os agendamentos futuros antes de mudar a agenda."
                )
                % {"momento": date_format(problema, "SHORT_DATETIME_FORMAT")}
            )
        return data

    def _appointment_outside(self, start, end, intervalo):
        """Start of the first future appointment the new settings would leave out, if any.

        Past appointments are not checked: the history may have other hours.
        """
        from apps.schedule.models import Appointment

        def minutos(hour):
            return hour.hour * 60 + hour.minute

        base = minutos(start)
        if self.instance.pk is None:
            return None
        # Django Admin runs without the request's clinic isolation. Validate only the
        # clinic being edited, including when this form is used outside a request.
        futuros = Appointment.all_objects.filter(
            clinic=self.instance, end__gt=timezone.now()
        ).order_by("start")
        for comeca, termina in futuros.values_list("start", "end"):
            comeca, termina = timezone.localtime(comeca), timezone.localtime(termina)
            horas = (comeca.time(), termina.time())
            fora = comeca.time() < start or (
                termina.time() > end and termina.time() != datetime.time(0)
            )
            desalinhado = any((minutos(h) - base) % intervalo or h.second for h in horas)
            if fora or desalinhado:
                return comeca
        return None


class NewClinicForm(ClinicModulesForm):
    """The installation's clinic, registered on the first access (decision 069). The
    schedule and the rest are set later in the clinic settings, the general modules
    included: a new clinic starts with all of them on."""

    document = document_field()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["general_modules"]

    def _chosen(self):
        return {*self.cleaned_data.get("modules", ()), *GENERAL_MODULES}

    def save(self, commit=True):
        # A new installation starts requiring two-step verification (decision 112).
        self.instance.require_two_factor = True
        return super().save(commit)

    class Meta:
        model = Clinic
        fields = [
            "name",
            "area",
            "country",
            "document",
            "email",
            "phone",
            "address",
            "currency",
            "time_zone",
        ]


class ClinicAdminForm(ClinicForm):
    class Meta(ClinicForm.Meta):
        fields = [*ClinicForm.Meta.fields, "active"]
