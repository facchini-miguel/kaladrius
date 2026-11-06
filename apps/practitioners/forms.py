from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.core import countries, identification
from apps.core.forms import BootstrapForm

from .models import Practitioner


class PractitionerForm(BootstrapForm, forms.ModelForm):
    class Meta:
        model = Practitioner
        fields = ["name", "registration", "color", "user", "active"]
        widgets = {"color": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinic_id is None:
            self.instance.clinic = clinic
        # The registrations of the clinic's country as examples (decision 121).
        examples = identification.for_country(
            countries.clinic_country(clinic)
        ).professional_registration
        self.fields["registration"].help_text = examples
        # Only users with an active membership in this clinic can be linked.
        self.fields["user"].queryset = (
            get_user_model()
            .objects.filter(memberships__clinic=clinic, memberships__active=True)
            .order_by("username")
            .distinct()
        )

    def clean_user(self):
        user = self.cleaned_data.get("user")
        if user is not None:
            others = Practitioner.objects.filter(user=user).exclude(pk=self.instance.pk)
            if others.exists():
                raise forms.ValidationError(
                    _("Este usuário já está ligado a outro profissional desta clínica.")
                )
        return user
