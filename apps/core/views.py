from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from . import painel
from .forms import ClinicaForm, NovaClinicaForm, TrocaSenhaForm
from .models import Clinica
from .permissoes import Acao, Modulo, exige_permissao


def _saudacao():
    hora = timezone.localtime().hour
    if hora < 12:
        return _("Bom dia")
    if hora < 18:
        return _("Boa tarde")
    return _("Boa noite")


@login_required
def inicio(request):
    contexto = {"saudacao": _saudacao()}
    if request.clinica is not None:
        contexto["painel"] = painel.montar(request)
    return render(request, "core/inicio.html", contexto)


def _destino_seguro(request, destino):
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return destino
    return "inicio"


@login_required
def cadastrar_clinica(request):
    """First access of a new installation: the superuser registers the clinic. There is
    only one (decision 069), so once it exists this page sends to the home page."""
    if not request.user.is_superuser:
        raise PermissionDenied
    if Clinica.objects.exists():
        return redirect("inicio")
    form = NovaClinicaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request, _("Clínica cadastrada. Agora cadastre a equipe em Cadastros > Equipe.")
        )
        return redirect("inicio")
    return render(request, "core/cadastrar_clinica.html", {"form": form})


class TrocarSenhaView(PasswordChangeView):
    """Any logged-in user can change their own password (keeps the session open)."""

    form_class = TrocaSenhaForm
    template_name = "core/trocar_senha.html"
    success_url = reverse_lazy("inicio")

    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, "demonstracao", False):
            messages.info(request, _("Contas de demonstração não trocam a senha."))
            return redirect("inicio")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, _("Senha alterada."))
        return super().form_valid(form)


@exige_permissao(Modulo.CLINICA, Acao.ALTERAR)
def configuracoes(request):
    form = ClinicaForm(request.POST or None, instance=request.clinica)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Configurações da clínica salvas."))
        return redirect("configuracoes")
    return render(request, "core/configuracoes.html", {"form": form})


@login_required
@require_POST
def trocar_idioma(request):
    """Save the user's language (empty: follow the browser) and go back to the page."""
    idioma = request.POST.get("idioma", "")
    if idioma not in dict(settings.LANGUAGES):
        idioma = ""
    request.user.idioma = idioma
    request.user.save(update_fields=["idioma"])
    resposta = redirect(_destino_seguro(request, request.POST.get("next")))
    # The cookie keeps the language on the login page of this browser too.
    if idioma:
        resposta.set_cookie(
            settings.LANGUAGE_COOKIE_NAME, idioma, max_age=365 * 24 * 3600, samesite="Lax"
        )
    else:
        resposta.delete_cookie(settings.LANGUAGE_COOKIE_NAME)
    return resposta
