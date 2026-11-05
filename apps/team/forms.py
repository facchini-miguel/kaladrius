from django import forms
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from apps.core.forms import BootstrapForm
from apps.core.models import Membership, Role, Usuario


def exclusive_account(user, clinic):
    """Whether the clinic administrator may manage the account itself (name, e-mail, password).

    Only for accounts used solely in this clinic: changing the password of someone who
    also works in another clinic, or of a platform administrator, would let one clinic
    take over access to the others.
    """
    return (
        not user.is_superuser
        and not user.is_staff
        and not user.vinculos.exclude(clinic=clinic).exists()
    )


class NewMemberForm(BootstrapForm, UserCreationForm):
    """A new user account, created already linked to the current clinic with a role."""

    role = forms.ChoiceField(label=_("Perfil"), choices=Role.choices, initial=Role.FRONT_DESK)

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ["username", "first_name", "last_name", "email"]

    def __init__(self, *args, clinic, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinic = clinic
        self.fields["first_name"].required = True

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            Membership.objects.create(user=user, clinic=self.clinic, role=self.cleaned_data["role"])
        return user


class MembershipForm(BootstrapForm, forms.ModelForm):
    """Role and access of a member in the current clinic."""

    class Meta:
        model = Membership
        fields = ["role", "active"]
        labels = {"active": _("Acesso a esta clínica liberado")}

    def __init__(self, *args, editor, **kwargs):
        super().__init__(*args, **kwargs)
        self.proprio = self.instance.user_id == editor.pk
        if self.proprio:
            # Nobody removes their own administrator role or access by accident.
            for field in self.fields.values():
                field.disabled = True
                field.help_text = _("Você não pode alterar o próprio perfil.")

    def clean(self):
        data = super().clean()
        era_admin_ativo = self.initial.get("role") == Role.ADMIN and self.initial.get("active")
        continua_admin = data.get("role") == Role.ADMIN and data.get("active")
        if era_admin_ativo and not continua_admin:
            # An account disabled for the whole platform cannot log in, so it does not count.
            outros = Membership.objects.filter(
                clinic_id=self.instance.clinic_id,
                role=Role.ADMIN,
                active=True,
                user__is_active=True,
            ).exclude(pk=self.instance.pk)
            if not outros.exists():
                raise forms.ValidationError(
                    _("A clínica precisa de pelo menos um administrador ativo.")
                )
        return data


class UserAccountForm(BootstrapForm, forms.ModelForm):
    """Name and e-mail of an account used only in this clinic."""

    class Meta:
        model = Usuario
        fields = ["first_name", "last_name", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_name"].required = True


class PasswordForm(BootstrapForm, SetPasswordForm):
    """New password set by the clinic administrator (the member's other sessions end)."""
