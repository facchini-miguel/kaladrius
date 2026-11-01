import datetime
import re

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.db import transaction
from django.utils import timezone
from django.utils.formats import date_format, get_format
from django.utils.translation import gettext_lazy as _

from . import moedas, paises
from .models import ESPECIALIDADES, MODULOS_GERAIS, Clinica, ModuloClinico, ModuloDaClinica
from .modulos import configurar, faltando, iniciais
from .validadores import cnpj_valido, cpf_valido, normalizar_cnpj


def _opcoes(grupo):
    return [(valor, nome) for valor, nome in ModuloClinico.choices if valor in grupo]


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
        # The currency symbols of apps/core/moedas.py (R$, US$, €, $U, S/, ₲...) and spaces;
        # anything else stays, so "abc" is still refused.
        for simbolo in moedas.SIMBOLOS:
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
        for nome in self.errors:
            if nome in self.fields:
                widget = self.fields[nome].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


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
            ModuloDaClinica.todos.filter(clinica=self.instance, ativo=True).values_list(
                "codigo", flat=True
            )
            if self.instance.pk
            else iniciais(self.instance.area)
        )
        self.initial["modulos"] = sorted(ligados & ESPECIALIDADES)
        self.initial["modulos_gerais"] = sorted(ligados & MODULOS_GERAIS)
        # The screen always sends them; a page opened before the update does not, and then
        # the clinic keeps its currency, country and time zone (Brazil's for a new one).
        for campo in ("moeda", "pais", "fuso_horario"):
            if campo in self.fields:
                self.fields[campo].required = False
        # CPF/CNPJ only for a Brazilian clinic; each country's documents are phase 2 (decision 117).
        if "documento" in self.fields and self._pais_escolhido() != "BR":
            del self.fields["documento"]

    def _pais_escolhido(self):
        if self.is_bound and self.data.get(self.add_prefix("pais")):
            return self.data[self.add_prefix("pais")]
        return self.instance.pais or paises.PADRAO

    def clean_moeda(self):
        return self.cleaned_data.get("moeda") or self.instance.moeda or moedas.PADRAO

    def clean_pais(self):
        return self.cleaned_data.get("pais") or self.instance.pais or paises.PADRAO

    def _ajustar_ao_pais(self, dados):
        """Time zone and currency of a new country (decision 117): a time zone of another country
        is refused; left as it was, it becomes the new country's first. The currency follows the
        country when it was still the previous country's default and was not changed now."""
        if "pais" not in dados:
            return
        pais = paises.do_codigo(dados["pais"])
        fuso = dados.get("fuso_horario")
        if "fuso_horario" in self.fields and fuso and fuso not in pais.fusos:
            if "fuso_horario" in self.changed_data:
                self.add_error(
                    "fuso_horario",
                    _("Escolha um fuso horário de %(pais)s.") % {"pais": pais.nome},
                )
            else:
                dados["fuso_horario"] = pais.fusos[0]
        elif not fuso:
            atual = self.instance.fuso_horario
            dados["fuso_horario"] = atual if atual in pais.fusos else pais.fusos[0]
        anterior = paises.do_codigo(self.instance.pais)
        if (
            "pais" in self.changed_data
            and "moeda" not in self.changed_data
            and dados.get("moeda") == anterior.moeda
        ):
            dados["moeda"] = pais.moeda

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

    # Typed with punctuation (up to 18 characters), stored as 11 or 14.
    documento = forms.CharField(label=_("CPF/CNPJ"), max_length=18, required=False)

    class Meta:
        model = Clinica
        fields = [
            "nome",
            "area",
            "pais",
            "documento",
            "email",
            "telefone",
            "endereco",
            "moeda",
            "fuso_horario",
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
    schedule and the rest are set later in the clinic settings, the general modules
    included: a new clinic starts with all of them on."""

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
        model = Clinica
        fields = [
            "nome",
            "area",
            "pais",
            "documento",
            "email",
            "telefone",
            "endereco",
            "moeda",
            "fuso_horario",
        ]


class ClinicaAdminForm(ClinicaForm):
    class Meta(ClinicaForm.Meta):
        fields = [*ClinicaForm.Meta.fields, "ativa"]
