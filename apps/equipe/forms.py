from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm

from apps.core.forms import FormularioBootstrap
from apps.core.models import Papel, Usuario, Vinculo


def conta_exclusiva(usuario, clinica):
    """Whether the clinic administrator may manage the account itself (name, e-mail, password).

    Only for accounts used solely in this clinic: changing the password of someone who
    also works in another clinic, or of a platform administrator, would let one clinic
    take over access to the others.
    """
    return (
        not usuario.is_superuser
        and not usuario.is_staff
        and not usuario.vinculos.exclude(clinica=clinica).exists()
    )


class NovoMembroForm(FormularioBootstrap, UserCreationForm):
    """A new user account, created already linked to the current clinic with a role."""

    papel = forms.ChoiceField(label="Perfil", choices=Papel.choices, initial=Papel.RECEPCAO)

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ["username", "first_name", "last_name", "email"]

    def __init__(self, *args, clinica, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinica = clinica
        self.fields["first_name"].required = True

    def save(self, commit=True):
        usuario = super().save(commit=commit)
        if commit:
            Vinculo.objects.create(
                usuario=usuario, clinica=self.clinica, papel=self.cleaned_data["papel"]
            )
        return usuario


class VinculoForm(FormularioBootstrap, forms.ModelForm):
    """Role and access of a member in the current clinic."""

    class Meta:
        model = Vinculo
        fields = ["papel", "ativo"]
        labels = {"ativo": "Acesso a esta clínica liberado"}

    def __init__(self, *args, editor, **kwargs):
        super().__init__(*args, **kwargs)
        self.proprio = self.instance.usuario_id == editor.pk
        if self.proprio:
            # Nobody removes their own administrator role or access by accident.
            for campo in self.fields.values():
                campo.disabled = True
                campo.help_text = "Você não pode alterar o próprio perfil."

    def clean(self):
        dados = super().clean()
        era_admin_ativo = self.initial.get("papel") == Papel.ADMIN and self.initial.get("ativo")
        continua_admin = dados.get("papel") == Papel.ADMIN and dados.get("ativo")
        if era_admin_ativo and not continua_admin:
            # An account disabled for the whole platform cannot log in, so it does not count.
            outros = Vinculo.objects.filter(
                clinica_id=self.instance.clinica_id,
                papel=Papel.ADMIN,
                ativo=True,
                usuario__is_active=True,
            ).exclude(pk=self.instance.pk)
            if not outros.exists():
                raise forms.ValidationError(
                    "A clínica precisa de pelo menos um administrador ativo."
                )
        return dados


class ContaForm(FormularioBootstrap, forms.ModelForm):
    """Name and e-mail of an account used only in this clinic."""

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True


class SenhaForm(FormularioBootstrap, SetPasswordForm):
    """New password set by the clinic administrator (the member's other sessions end)."""
