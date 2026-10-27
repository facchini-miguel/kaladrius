from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .forms import ClinicaForm, TrocaSenhaForm
from .middleware import SESSAO_CLINICA, clinicas_do_usuario
from .permissoes import Acao, Modulo, exige_permissao


@login_required
def inicio(request):
    return render(request, "core/inicio.html")


def _destino_seguro(request, destino):
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return destino
    return "inicio"


@login_required
def trocar_clinica(request):
    clinicas = clinicas_do_usuario(request.user)
    destino = _destino_seguro(request, request.POST.get("next") or request.GET.get("next"))
    if request.method == "POST":
        escolhida = request.POST.get("clinica", "")
        clinica = clinicas.filter(pk=escolhida).first() if escolhida.isdecimal() else None
        if clinica is None:
            raise PermissionDenied
        request.session[SESSAO_CLINICA] = clinica.pk
        messages.success(
            request, _("Você está trabalhando na clínica %(nome)s.") % {"nome": clinica.nome}
        )
        return redirect(destino)
    return render(request, "core/trocar_clinica.html", {"clinicas": clinicas, "next": destino})


class TrocarSenhaView(PasswordChangeView):
    """Any logged-in user can change their own password (keeps the session open)."""

    form_class = TrocaSenhaForm
    template_name = "core/trocar_senha.html"
    success_url = reverse_lazy("inicio")

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
