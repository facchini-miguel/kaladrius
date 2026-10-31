from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.core.forms import FormularioBootstrap
from apps.pacientes.models import Paciente
from apps.profissionais.models import Profissional

from . import servicos
from .models import Agendamento, TipoAtendimento


class TipoAtendimentoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = TipoAtendimento
        fields = ["nome", "cor", "ativo"]
        widgets = {"cor": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinica_id is None:
            self.instance.clinica = clinica

    def clean_nome(self):
        # The clinic is not a form field, so the unique constraint must be checked here.
        nome = self.cleaned_data["nome"].strip()
        repetido = TipoAtendimento.objects.filter(nome__iexact=nome).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise forms.ValidationError(_("Já existe um tipo de atendimento com este nome."))
        return nome


class AgendamentoForm(FormularioBootstrap, forms.ModelForm):
    data = forms.DateField(
        label=_("Data"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    hora_inicio = forms.TimeField(
        label=pgettext_lazy("hora", "Início"),
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
    )
    hora_fim = forms.TimeField(
        label=_("Fim"), widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
    )
    repeticoes = forms.IntegerField(
        label=_("Repetir por quantas semanas"),
        min_value=1,
        max_value=52,
        initial=1,
        help_text=_("1 = somente nesta data. Ex.: 4 cria o mesmo horário por 4 semanas seguidas."),
    )

    class Meta:
        model = Agendamento
        fields = ["profissional", "tipo", "paciente", "descricao"]
        widgets = {
            "paciente": forms.HiddenInput,
            "descricao": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, clinica, profissionais=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinica = clinica
        self.intervalos = []
        agendamento = self.instance
        if agendamento.clinica_id is None:
            agendamento.clinica = clinica

        # Inactive practitioners/types are hidden, except the ones already in use here.
        if profissionais is None:
            profissionais = Profissional.objects.all()
        self.fields["profissional"].queryset = profissionais.filter(
            Q(ativo=True) | Q(pk=agendamento.profissional_id)
        )
        self.fields["tipo"].queryset = TipoAtendimento.objects.filter(
            Q(ativo=True) | Q(pk=agendamento.tipo_id)
        )
        self.fields["paciente"].queryset = Paciente.objects.all()

        passo = clinica.agenda_intervalo * 60
        for campo in ("hora_inicio", "hora_fim"):
            self.fields[campo].widget.attrs.update(
                step=passo,
                min=clinica.agenda_inicio.strftime("%H:%M"),
                max=clinica.agenda_fim.strftime("%H:%M"),
            )

        if agendamento.pk:
            del self.fields["repeticoes"]  # recurrence only applies when creating
            inicio = timezone.localtime(agendamento.inicio)
            self.initial.update(
                data=inicio.date(),
                hora_inicio=inicio.time(),
                hora_fim=timezone.localtime(agendamento.fim).time(),
            )

    def _alinhado(self, hora):
        inicio = self.clinica.agenda_inicio
        minutos = (hora.hour * 60 + hora.minute) - (inicio.hour * 60 + inicio.minute)
        return hora.second == 0 and minutos % self.clinica.agenda_intervalo == 0

    def clean(self):
        dados = super().clean()
        data, hora_inicio, hora_fim = (
            dados.get("data"),
            dados.get("hora_inicio"),
            dados.get("hora_fim"),
        )
        if not dados.get("paciente") and not dados.get("descricao", "").strip():
            self.add_error("descricao", _("Informe o paciente ou uma descrição."))
        paciente = dados.get("paciente")
        if (
            self.instance.pk
            and self.instance.desmarcado
            and (getattr(paciente, "pk", None) != self.instance.paciente_id)
        ):
            # Changing the patient would overwrite the record that this one cancelled.
            self.add_error(
                "paciente",
                _(
                    "Este agendamento foi desmarcado. Para pôr outro paciente neste horário, "
                    "use “Agendar outro paciente neste horário”."
                ),
            )
        if None in (data, hora_inicio, hora_fim) or self.errors:
            return dados

        clinica = self.clinica
        if hora_fim <= hora_inicio:
            self.add_error("hora_fim", _("O fim deve ser depois do início."))
            return dados
        intervalo = clinica.agenda_intervalo
        for campo, hora in (("hora_inicio", hora_inicio), ("hora_fim", hora_fim)):
            if not self._alinhado(hora):
                self.add_error(
                    campo, _("Use horários de %(n)s em %(n)s minutos.") % {"n": intervalo}
                )
        if hora_inicio < clinica.agenda_inicio or hora_fim > clinica.agenda_fim:
            self.add_error(
                None,
                _("Fora do horário de atendimento da clínica (%(inicio)s às %(fim)s).")
                % {
                    "inicio": f"{clinica.agenda_inicio:%H:%M}",
                    "fim": f"{clinica.agenda_fim:%H:%M}",
                },
            )
        if self.errors:
            return dados

        self.intervalos = servicos.ocorrencias(
            data, hora_inicio, hora_fim, dados.get("repeticoes") or 1
        )
        self.instance.inicio, self.instance.fim = self.intervalos[0]
        marcado = (Agendamento.Situacao.COMPARECEU, Agendamento.Situacao.FALTOU)
        if not dados.get("paciente") or (
            self.instance.situacao in marcado and data > timezone.localdate()
        ):
            # Without a patient there is nothing to mark; moved to a future day, nobody
            # came or missed it yet.
            self.instance.situacao = Agendamento.Situacao.AGENDADO
        if self.instance.desmarcado:
            # A cancelled appointment does not hold the slot, so it conflicts with nothing.
            return dados
        encontrados = servicos.conflitos(
            dados["profissional"], self.intervalos, ignorar=self.instance.pk
        )
        if encontrados:
            lista = "; ".join(
                f"{date_format(timezone.localtime(a.inicio), 'SHORT_DATETIME_FORMAT')} ({a.titulo})"
                for a in encontrados[:5]
            )
            if len(encontrados) > 5:
                lista += " " + _("e mais %(n)s") % {"n": len(encontrados) - 5}
            raise forms.ValidationError(
                _("Conflito de horário com: %(lista)s. Nada foi gravado.") % {"lista": lista}
            )
        return dados
