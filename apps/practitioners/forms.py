from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.core import countries, identification
from apps.core.forms import FormularioBootstrap

from .models import Practitioner


class ProfissionalForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Practitioner
        fields = ["name", "registro", "cor", "user", "active"]
        widgets = {"cor": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinic_id is None:
            self.instance.clinic = clinic
        # The registrations of the clinic's country as examples (decision 121).
        exemplos = identification.do_pais(countries.pais_da_clinica(clinic)).registro_profissional
        self.fields["registro"].help_text = exemplos
        # Only users with an active membership in this clinic can be linked.
        self.fields["user"].queryset = (
            get_user_model()
            .objects.filter(vinculos__clinic=clinic, vinculos__active=True)
            .order_by("username")
            .distinct()
        )

    def clean_user(self):
        user = self.cleaned_data.get("user")
        if user is not None:
            outros = Practitioner.objects.filter(user=user).exclude(pk=self.instance.pk)
            if outros.exists():
                raise forms.ValidationError(
                    _("Este usuário já está ligado a outro profissional desta clínica.")
                )
        return user
