from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.forms import BootstrapForm

from . import services


class EntrarForm(AuthenticationForm):
    """The login, also refused after too many wrong attempts from the same address."""

    def clean(self):
        if self.request is not None and services.endereco_bloqueado(self.request):
            raise ValidationError(
                _("Muitas tentativas erradas a partir deste endereço. Tente de novo em 1 hora."),
                code="endereco_bloqueado",
            )
        return super().clean()


def _campo_codigo(label):
    return forms.CharField(
        label=label,
        max_length=20,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "autofocus": True}),
    )


class CodigoForm(BootstrapForm, forms.Form):
    code = _campo_codigo(_("Código"))


class DesativarForm(BootstrapForm, forms.Form):
    senha = forms.CharField(label=_("Sua senha"), widget=forms.PasswordInput)
    code = _campo_codigo(_("Código do aplicativo"))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        data = super().clean()
        if data.get("senha") and not self.user.check_password(data["senha"]):
            self.add_error("senha", _("Senha incorreta."))
        elif data.get("code") and not services.verificar(self.user, data["code"]):
            self.add_error("code", _("Código incorreto."))
        return data


class RecuperarSenhaForm(BootstrapForm, PasswordResetForm):
    """Password recovery by e-mail, never for the public demo logins."""

    def get_users(self, email):
        return (user for user in super().get_users(email) if not user.demo)


class NovaSenhaForm(BootstrapForm, SetPasswordForm):
    pass
