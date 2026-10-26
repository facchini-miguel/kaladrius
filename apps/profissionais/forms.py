from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import FormularioBootstrap

from .models import Profissional


class ProfissionalForm(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Profissional
        fields = ["nome", "registro", "cor", "usuario", "ativo"]
        widgets = {"cor": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.clinica_id is None:
            self.instance.clinica = clinica
        # Only users with an active membership in this clinic can be linked.
        self.fields["usuario"].queryset = (
            get_user_model()
            .objects.filter(vinculos__clinica=clinica, vinculos__ativo=True)
            .order_by("username")
            .distinct()
        )

    def clean_usuario(self):
        usuario = self.cleaned_data.get("usuario")
        if usuario is not None:
            outros = Profissional.objects.filter(usuario=usuario).exclude(pk=self.instance.pk)
            if outros.exists():
                raise forms.ValidationError(
                    "Este usuário já está ligado a outro profissional desta clínica."
                )
        return usuario
