from django import forms
from django.db.models import Q
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from apps.core.forms import BootstrapForm
from apps.patients.models import Patient
from apps.practitioners.models import Practitioner

from . import services
from .models import Appointment, AppointmentType


class AppointmentTypeForm(BootstrapForm, forms.ModelForm):
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
        repeated = AppointmentType.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if repeated.exists():
            raise forms.ValidationError(_("An appointment type with this name already exists."))
        return name


class AppointmentForm(BootstrapForm, forms.ModelForm):
    date = forms.DateField(
        label=_("Date"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")
    )
    start_time = forms.TimeField(
        label=pgettext_lazy("time", "Start"),
        widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
    )
    end_time = forms.TimeField(
        label=_("End"), widget=forms.TimeInput(attrs={"type": "time"}, format="%H:%M")
    )
    repetitions = forms.IntegerField(
        label=_("Repeat for how many weeks"),
        min_value=1,
        max_value=52,
        initial=1,
        help_text=_(
            "1 = only on this date. E.g.: 4 creates the same time slot for 4 weeks in a row."
        ),
    )

    class Meta:
        model = Appointment
        fields = ["practitioner", "kind", "patient", "description"]
        widgets = {
            "patient": forms.HiddenInput,
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, clinic, practitioners=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinic = clinic
        self.intervals = []
        appointment = self.instance
        if appointment.clinic_id is None:
            appointment.clinic = clinic

        # Inactive practitioners/types are hidden, except the ones already in use here.
        if practitioners is None:
            practitioners = Practitioner.objects.all()
        self.fields["practitioner"].queryset = practitioners.filter(
            Q(active=True) | Q(pk=appointment.practitioner_id)
        )
        self.fields["kind"].queryset = AppointmentType.objects.filter(
            Q(active=True) | Q(pk=appointment.kind_id)
        )
        self.fields["kind"].label_from_instance = lambda kind: kind.display_name
        self.fields["patient"].queryset = Patient.objects.all()

        step = clinic.schedule_interval * 60
        for field in ("start_time", "end_time"):
            self.fields[field].widget.attrs.update(
                step=step,
                min=clinic.schedule_start.strftime("%H:%M"),
                max=clinic.schedule_end.strftime("%H:%M"),
            )

        if appointment.pk:
            del self.fields["repetitions"]  # recurrence only applies when creating
            start = timezone.localtime(appointment.start)
            self.initial.update(
                date=start.date(),
                start_time=start.time(),
                end_time=timezone.localtime(appointment.end).time(),
            )

    def _aligned(self, hour):
        start = self.clinic.schedule_start
        minutes = (hour.hour * 60 + hour.minute) - (start.hour * 60 + start.minute)
        return hour.second == 0 and minutes % self.clinic.schedule_interval == 0

    def clean(self):
        data = super().clean()
        date, start_time, end_time = (
            data.get("date"),
            data.get("start_time"),
            data.get("end_time"),
        )
        if not data.get("patient") and not data.get("description", "").strip():
            self.add_error("description", _("Enter the patient or a description."))
        patient = data.get("patient")
        if (
            self.instance.pk
            and self.instance.is_cancelled
            and (getattr(patient, "pk", None) != self.instance.patient_id)
        ):
            # Changing the patient would overwrite the record that this one cancelled.
            self.add_error(
                "patient",
                _(
                    "This appointment was cancelled. To put another patient at this time, use "
                    "“Book another patient at this time”."
                ),
            )
        if None in (date, start_time, end_time) or self.errors:
            return data

        clinic = self.clinic
        if end_time <= start_time:
            self.add_error("end_time", _("The end must be after the start."))
            return data
        interval = clinic.schedule_interval
        for field, hour in (("start_time", start_time), ("end_time", end_time)):
            if not self._aligned(hour):
                self.add_error(field, _("Use times in steps of %(n)s minutes.") % {"n": interval})
        if start_time < clinic.schedule_start or end_time > clinic.schedule_end:
            self.add_error(
                None,
                _("Outside the clinic's opening hours (%(inicio)s to %(fim)s).")
                % {
                    "inicio": f"{clinic.schedule_start:%H:%M}",
                    "fim": f"{clinic.schedule_end:%H:%M}",
                },
            )
        if self.errors:
            return data

        self.intervals = services.occurrences(
            date, start_time, end_time, data.get("repetitions") or 1
        )
        self.instance.start, self.instance.end = self.intervals[0]
        marked = (Appointment.Status.ATTENDED, Appointment.Status.MISSED)
        if not data.get("patient") or (
            self.instance.status in marked and date > timezone.localdate()
        ):
            # Without a patient there is nothing to mark; moved to a future day, nobody
            # came or missed it yet.
            self.instance.status = Appointment.Status.BOOKED
        if self.instance.is_cancelled:
            # A cancelled appointment does not hold the slot, so it conflicts with nothing.
            return data
        found = services.conflicts(data["practitioner"], self.intervals, ignore=self.instance.pk)
        if found:
            results = "; ".join(
                f"{date_format(timezone.localtime(a.start), 'SHORT_DATETIME_FORMAT')} ({a.title})"
                for a in found[:5]
            )
            if len(found) > 5:
                results += " " + _("and %(n)s more") % {"n": len(found) - 5}
            raise forms.ValidationError(
                _("Time conflict with: %(lista)s. Nothing was saved.") % {"lista": results}
            )
        return data
