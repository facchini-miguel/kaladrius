import datetime
import re

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format, get_format
from django.utils.translation import gettext_lazy as _

from . import countries, currencies, identification
from .models import ESPECIALIDADES, MODULOS_GERAIS, Clinic, ClinicModule, ModuloClinico
from .modules import configurar, faltando, iniciais


def _opcoes(group):
    return [(value, name) for value, name in ModuloClinico.choices if value in group]


class CampoDecimal(forms.DecimalField):
    """A number typed the way people write it: "1.500,00", "R$ 1.500,00", "€ 1.500" or "1500,00" in
    Portuguese and Spanish ("1,500.00" in English). Django's own field refused the
    thousands separator ("Informe um número."), and "1.500" read as one and a half.
    """

    def to_python(self, value):
        if isinstance(value, str):
            value = self._sem_milhar(value)
        return super().to_python(value)

    @staticmethod
    def _sem_milhar(texto):
        # The currency symbols of apps/core/currencies.py (R$, US$, €, $U, S/, ₲...) and spaces;
        # anything else stays, so "abc" is still refused.
        for simbolo in currencies.SIMBOLOS:
            texto = texto.replace(simbolo, "")
        texto = re.sub(r"\s", "", texto)
        decimal = get_format("DECIMAL_SEPARATOR")
        milhar = "." if decimal == "," else ","
        grupos = rf"-?\d{{1,3}}(\{milhar}\d{{3}})+"
        if decimal in texto or re.fullmatch(grupos, texto):
            # "1.500,00" and "1.500": the dots group thousands.
            return texto.replace(milhar, "")
        # "1500.00": a lone point is taken as the decimal mark, whatever the language.
        return texto if decimal == "," else texto.replace(milhar, decimal)


class FormularioBootstrap:
    """Mixin that adds Bootstrap 5 classes to every widget of a form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            if type(campo) is forms.DecimalField:
                campo.__class__ = CampoDecimal
            # Django 6.1's "- Select an option -" has no Portuguese translation yet: the
            # blank option of every list becomes a dash, from a table or fixed choices.
            if isinstance(campo, forms.ModelChoiceField):
                if campo.empty_label is not None:
                    campo.empty_label = "—"
            elif isinstance(campo, forms.ChoiceField):
                opcoes = list(campo.choices)
                if opcoes and opcoes[0][0] in ("", None) and not isinstance(opcoes[0][1], list):
                    campo.choices = [("", "—"), *opcoes[1:]]
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
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


def campo_documento():
    """A document of the clinic's country, typed with or without punctuation (decision 121).
    The form names it and checks it (apps/core/identification.py)."""
    return forms.CharField(
        label=_("Documento"),
        max_length=25,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )


def documento_por_tipo(campo, individuo, empresa, kind):
    """Name and example of a document field that depends on the person type: the document of
    an individual and of a company (either may be None, and then the field is hidden for that
    type). The page switches them when the type changes (static/js/page.js)."""
    atual = empresa if kind == "PJ" else individuo
    campo.label = (atual or individuo or empresa).sigla
    campo.widget.attrs.update(
        {
            "data-rotulo-pf": individuo.sigla if individuo else "",
            "data-rotulo-pj": empresa.sigla if empresa else "",
            "data-exemplo-pf": individuo.exemplo if individuo else "",
            "data-exemplo-pj": empresa.exemplo if empresa else "",
            "placeholder": atual.exemplo if atual else "",
        }
    )


class TrocaSenhaForm(FormularioBootstrap, PasswordChangeForm):
    """The user's own password change, with Bootstrap styling."""


class ModulosClinicosForm(FormularioBootstrap, forms.ModelForm):
    """Specialties and general modules of the clinic (decision 092)."""

    modulos = forms.MultipleChoiceField(
        label=_("Especialidades"),
        choices=_opcoes(ESPECIALIDADES),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        help_text=_(
            "Só Odontologia, só Medicina ou as duas juntas (ou nenhuma, em outra área da "
            "saúde). Desativar não apaga o histórico."
        ),
    )
    modulos_gerais = forms.MultipleChoiceField(
        label=_("Módulos"),
        choices=_opcoes(MODULOS_GERAIS),
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
            ClinicModule.todos.filter(clinic=self.instance, active=True).values_list(
                "code", flat=True
            )
            if self.instance.pk
            else iniciais(self.instance.area)
        )
        self.initial["modulos"] = sorted(ligados & ESPECIALIDADES)
        self.initial["modulos_gerais"] = sorted(ligados & MODULOS_GERAIS)
        # The screen always sends them; a page opened before the update does not, and then
        # the clinic keeps its currency, country and time zone (Brazil's for a new one).
        for campo in ("moeda", "pais", "fuso_horario", "numeracao_dentaria"):
            if campo in self.fields:
                self.fields[campo].required = False
        # The country's tax document, an individual's or a company's (decision 121): "CPF/CNPJ"
        # in Brazil, "EIN" in the United States... of the country chosen now.
        if "documento" in self.fields:
            documentos = identification.do_pais(self._pais_escolhido())
            self.documentos_da_clinica = documentos.de("pessoa", "empresa")
            campo = self.fields["documento"]
            campo.label = documentos.rotulo("pessoa", "empresa")
            campo.widget.attrs["placeholder"] = " · ".join(
                d.exemplo for d in self.documentos_da_clinica
            )

    def clean_documento(self):
        return identification.limpar(
            self.cleaned_data.get("documento", ""),
            self.documentos_da_clinica,
            self.fields["documento"].label,
        )

    def _pais_escolhido(self):
        if self.is_bound and self.data.get(self.add_prefix("pais")):
            return self.data[self.add_prefix("pais")]
        return self.instance.pais or countries.PADRAO

    def clean_moeda(self):
        return self.cleaned_data.get("moeda") or self.instance.moeda or currencies.PADRAO

    def clean_pais(self):
        return self.cleaned_data.get("pais") or self.instance.pais or countries.PADRAO

    def _ajustar_ao_pais(self, dados):
        """Time zone and currency of a new country (decision 117): a time zone of another country
        is refused; left as it was, it becomes the new country's first. The currency follows the
        country when it was still the previous country's default and was not changed now."""
        if "pais" not in dados:
            return
        pais = countries.do_codigo(dados["pais"])
        fuso = dados.get("fuso_horario")
        if "fuso_horario" in self.fields and fuso and fuso not in pais.fusos:
            if "fuso_horario" in self.changed_data:
                self.add_error(
                    "fuso_horario",
                    _("Escolha um fuso horário de %(pais)s.") % {"pais": pais.name},
                )
            else:
                dados["fuso_horario"] = pais.fusos[0]
        elif not fuso:
            atual = self.instance.fuso_horario
            dados["fuso_horario"] = atual if atual in pais.fusos else pais.fusos[0]
        anterior = countries.do_codigo(self.instance.pais)
        if (
            "pais" in self.changed_data
            and "moeda" not in self.changed_data
            and dados.get("moeda") == anterior.moeda
        ):
            dados["moeda"] = pais.moeda
        # The tooth numbering too (decision 122); a new clinic, without the field, gets its
        # country's.
        if "numeracao_dentaria" not in self.fields:
            self.instance.numeracao_dentaria = pais.numeracao
        else:
            atual = self.instance.numeracao_dentaria or anterior.numeracao
            escolhida = dados.get("numeracao_dentaria") or atual
            if "pais" in self.changed_data and escolhida == atual == anterior.numeracao:
                escolhida = pais.numeracao
            dados["numeracao_dentaria"] = escolhida

    def _escolhidos(self):
        return {*self.cleaned_data.get("modulos", ()), *self.cleaned_data.get("modulos_gerais", ())}

    def clean(self):
        dados = super().clean()
        self._ajustar_ao_pais(dados)
        for modulo, precisa in faltando(self._escolhidos()).items():
            self.add_error(
                "modulos_gerais",
                _("%(modulo)s precisa de: %(precisa)s.")
                % {
                    "modulo": ModuloClinico(modulo).label,
                    "precisa": ", ".join(str(ModuloClinico(p).label) for p in sorted(precisa)),
                },
            )
        return dados

    def _save_m2m(self):
        super()._save_m2m()
        configurar(self.instance, self._escolhidos())

    @transaction.atomic
    def save(self, commit=True):
        return super().save(commit=commit)


class ClinicaForm(ModulosClinicosForm):
    """Clinic details and schedule settings, changed by the clinic administrator."""

    documento = campo_documento()

    class Meta:
        model = Clinic
        fields = [
            "name",
            "area",
            "pais",
            "documento",
            "email",
            "phone",
            "endereco",
            "moeda",
            "fuso_horario",
            "numeracao_dentaria",
        ] + [
            "agenda_inicio",
            "agenda_fim",
            "agenda_intervalo",
            "exigir_duas_etapas",
        ]
        widgets = {
            "agenda_inicio": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
            "agenda_fim": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }
        help_texts = {
            "agenda_intervalo": _("Os agendamentos começam e terminam em múltiplos deste tempo."),
        }

    def clean(self):
        dados = super().clean()
        start, end = dados.get("agenda_inicio"), dados.get("agenda_fim")
        intervalo = dados.get("agenda_intervalo")
        if None in (start, end, intervalo):
            return dados
        if start >= end:
            self.add_error("agenda_fim", _("O fim da agenda deve ser depois do início."))
            return dados
        problema = self._agendamento_fora(start, end, intervalo)
        if problema is not None:
            raise forms.ValidationError(
                _(
                    "O agendamento de %(momento)s ficaria fora do novo horário ou do novo "
                    "intervalo. Ajuste os agendamentos futuros antes de mudar a agenda."
                )
                % {"momento": date_format(problema, "SHORT_DATETIME_FORMAT")}
            )
        return dados

    def _agendamento_fora(self, start, end, intervalo):
        """Start of the first future appointment the new settings would leave out, if any.

        Past appointments are not checked: the history may have other hours.
        """
        from apps.schedule.models import Appointment

        def minutos(hora):
            return hora.hour * 60 + hora.minute

        base = minutos(start)
        if self.instance.pk is None:
            return None
        # Django Admin runs without the request's clinic isolation. Validate only the
        # clinic being edited, including when this form is used outside a request.
        futuros = Appointment.todos.filter(clinic=self.instance, end__gt=timezone.now()).order_by(
            "start"
        )
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


class NovaClinicaForm(ModulosClinicosForm):
    """The installation's clinic, registered on the first access (decision 069). The
    schedule and the rest are set later in the clinic settings, the general modules
    included: a new clinic starts with all of them on."""

    documento = campo_documento()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields["modulos_gerais"]

    def _escolhidos(self):
        return {*self.cleaned_data.get("modulos", ()), *MODULOS_GERAIS}

    def save(self, commit=True):
        # A new installation starts requiring two-step verification (decision 112).
        self.instance.exigir_duas_etapas = True
        return super().save(commit)

    class Meta:
        model = Clinic
        fields = [
            "name",
            "area",
            "pais",
            "documento",
            "email",
            "phone",
            "endereco",
            "moeda",
            "fuso_horario",
        ]


class ClinicaAdminForm(ClinicaForm):
    class Meta(ClinicaForm.Meta):
        fields = [*ClinicaForm.Meta.fields, "active"]
