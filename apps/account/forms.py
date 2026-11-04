from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.forms import FormularioBootstrap

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


def _campo_codigo(rotulo):
    return forms.CharField(
        label=rotulo,
        max_length=20,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "autofocus": True}),
    )


class CodigoForm(FormularioBootstrap, forms.Form):
    codigo = _campo_codigo(_("Código"))


class DesativarForm(FormularioBootstrap, forms.Form):
    senha = forms.CharField(label=_("Sua senha"), widget=forms.PasswordInput)
    codigo = _campo_codigo(_("Código do aplicativo"))

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean(self):
        dados = super().clean()
        if dados.get("senha") and not self.user.check_password(dados["senha"]):
            self.add_error("senha", _("Senha incorreta."))
        elif dados.get("codigo") and not services.verificar(self.user, dados["codigo"]):
            self.add_error("codigo", _("Código incorreto."))
        return dados


class RecuperarSenhaForm(FormularioBootstrap, PasswordResetForm):
    """Password recovery by e-mail, never for the public demo logins."""

    def get_users(self, email):
        return (user for user in super().get_users(email) if not user.demonstracao)


class NovaSenhaForm(FormularioBootstrap, SetPasswordForm):
    pass
