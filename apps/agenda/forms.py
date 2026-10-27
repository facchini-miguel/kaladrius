from django import forms
from django.db.models import Q
from django.utils import timezone

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
            raise forms.ValidationError("Já existe um tipo de atendimento com este nome.")
        return nome


class AgendamentoForm(FormularioBootstrap, forms.ModelForm):
    data = forms.DateField(
        label="Data", widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    hora_inicio = forms.TimeField(
        label="Início", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
    )
    hora_fim = forms.TimeField(
        label="Fim", widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
    )
    repeticoes = forms.IntegerField(
        label="Repetir por quantas semanas",
        min_value=1,
        max_value=52,
        initial=1,
        help_text="1 = somente nesta data. Ex.: 4 cria o mesmo horário por 4 semanas seguidas.",
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
            self.add_error("descricao", "Informe o paciente ou uma descrição.")
        if None in (data, hora_inicio, hora_fim) or self.errors:
            return dados

        clinica = self.clinica
        if hora_fim <= hora_inicio:
            self.add_error("hora_fim", "O fim deve ser depois do início.")
            return dados
        intervalo = clinica.agenda_intervalo
        for campo, hora in (("hora_inicio", hora_inicio), ("hora_fim", hora_fim)):
            if not self._alinhado(hora):
                self.add_error(campo, f"Use horários de {intervalo} em {intervalo} minutos.")
        if hora_inicio < clinica.agenda_inicio or hora_fim > clinica.agenda_fim:
            self.add_error(
                None,
                f"Fora do horário de atendimento da clínica "
                f"({clinica.agenda_inicio:%H:%M} às {clinica.agenda_fim:%H:%M}).",
            )
        if self.errors:
            return dados

        self.intervalos = servicos.ocorrencias(
            data, hora_inicio, hora_fim, dados.get("repeticoes") or 1
        )
        self.instance.inicio, self.instance.fim = self.intervalos[0]
        encontrados = servicos.conflitos(
            dados["profissional"], self.intervalos, ignorar=self.instance.pk
        )
        if encontrados:
            lista = "; ".join(
                f"{timezone.localtime(a.inicio):%d/%m às %H:%M} ({a.titulo})"
                for a in encontrados[:5]
            )
            extra = f" e mais {len(encontrados) - 5}" if len(encontrados) > 5 else ""
            raise forms.ValidationError(
                f"Conflito de horário com: {lista}{extra}. Nada foi gravado."
            )
        return dados
