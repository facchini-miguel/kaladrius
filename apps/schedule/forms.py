from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.core.forms import FormularioBootstrap
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

from . import services
from .models import Appointment, AppointmentType


class TipoAtendimentoForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = AppointmentType
        fields = ["name", "color", "active"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinic_id is None:
            self.instance.clinic = clinic

    def clean_name(self):
        # The clinic is not a form field, so the unique constraint must be checked here.
        name = self.cleaned_data["name"].strip()
        repetido = AppointmentType.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if repetido.exists():
            raise forms.ValidationError(_("Já existe um tipo de atendimento com este nome."))
        return name


class AgendamentoForm(FormularioBootstrap, forms.ModelForm):
    date = forms.DateField(
        label=_("Data"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    start_time = forms.TimeField(
        label=pgettext_lazy("hora", "Início"),
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
    )
    end_time = forms.TimeField(
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
        model = Appointment
        fields = ["practitioner", "kind", "patient", "description"]
        widgets = {
            "patient": forms.HiddenInput,
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, clinic, profissionais=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinic = clinic
        self.intervalos = []
        appointment = self.instance
        if appointment.clinic_id is None:
            appointment.clinic = clinic

        # Inactive practitioners/types are hidden, except the ones already in use here.
        if profissionais is None:
            profissionais = Practitioner.objects.all()
        self.fields["practitioner"].queryset = profissionais.filter(
            Q(active=True) | Q(pk=appointment.practitioner_id)
        )
        self.fields["kind"].queryset = AppointmentType.objects.filter(
            Q(active=True) | Q(pk=appointment.kind_id)
        )
        self.fields["kind"].label_from_instance = lambda kind: kind.nome_exibido
        self.fields["patient"].queryset = Patient.objects.all()

        passo = clinic.schedule_interval * 60
        for campo in ("start_time", "end_time"):
            self.fields[campo].widget.attrs.update(
                step=passo,
                min=clinic.schedule_start.strftime("%H:%M"),
                max=clinic.schedule_end.strftime("%H:%M"),
            )

        if appointment.pk:
            del self.fields["repeticoes"]  # recurrence only applies when creating
            start = timezone.localtime(appointment.start)
            self.initial.update(
                date=start.date(),
                start_time=start.time(),
                end_time=timezone.localtime(appointment.end).time(),
            )

    def _alinhado(self, hora):
        start = self.clinic.schedule_start
        minutos = (hora.hour * 60 + hora.minute) - (start.hour * 60 + start.minute)
        return hora.second == 0 and minutos % self.clinic.schedule_interval == 0

    def clean(self):
        dados = super().clean()
        date, start_time, end_time = (
            dados.get("date"),
            dados.get("start_time"),
            dados.get("end_time"),
        )
        if not dados.get("patient") and not dados.get("description", "").strip():
            self.add_error("description", _("Informe o paciente ou uma descrição."))
        patient = dados.get("patient")
        if (
            self.instance.pk
            and self.instance.desmarcado
            and (getattr(patient, "pk", None) != self.instance.patient_id)
        ):
            # Changing the patient would overwrite the record that this one cancelled.
            self.add_error(
                "patient",
                _(
                    "Este agendamento foi desmarcado. Para pôr outro paciente neste horário, "
                    "use “Agendar outro paciente neste horário”."
                ),
            )
        if None in (date, start_time, end_time) or self.errors:
            return dados

        clinic = self.clinic
        if end_time <= start_time:
            self.add_error("end_time", _("O fim deve ser depois do início."))
            return dados
        intervalo = clinic.schedule_interval
        for campo, hora in (("start_time", start_time), ("end_time", end_time)):
            if not self._alinhado(hora):
                self.add_error(
                    campo, _("Use horários de %(n)s em %(n)s minutos.") % {"n": intervalo}
                )
        if start_time < clinic.schedule_start or end_time > clinic.schedule_end:
            self.add_error(
                None,
                _("Fora do horário de atendimento da clínica (%(inicio)s às %(fim)s).")
                % {
                    "inicio": f"{clinic.schedule_start:%H:%M}",
                    "fim": f"{clinic.schedule_end:%H:%M}",
                },
            )
        if self.errors:
            return dados

        self.intervalos = services.ocorrencias(
            date, start_time, end_time, dados.get("repeticoes") or 1
        )
        self.instance.start, self.instance.end = self.intervalos[0]
        marcado = (Appointment.Situacao.COMPARECEU, Appointment.Situacao.FALTOU)
        if not dados.get("patient") or (
            self.instance.status in marcado and date > timezone.localdate()
        ):
            # Without a patient there is nothing to mark; moved to a future day, nobody
            # came or missed it yet.
            self.instance.status = Appointment.Situacao.AGENDADO
        if self.instance.desmarcado:
            # A cancelled appointment does not hold the slot, so it conflicts with nothing.
            return dados
        encontrados = services.conflitos(
            dados["practitioner"], self.intervalos, ignorar=self.instance.pk
        )
        if encontrados:
            lista = "; ".join(
                f"{date_format(timezone.localtime(a.start), 'SHORT_DATETIME_FORMAT')} ({a.titulo})"
                for a in encontrados[:5]
            )
            if len(encontrados) > 5:
                lista += " " + _("e mais %(n)s") % {"n": len(encontrados) - 5}
            raise forms.ValidationError(
                _("Conflito de horário com: %(lista)s. Nada foi gravado.") % {"lista": lista}
            )
        return dados
