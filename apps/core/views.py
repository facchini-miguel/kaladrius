from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import TrocaSenhaForm
from .middleware import SESSAO_CLINICA, clinicas_do_usuario


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
        messages.success(request, f"Você está trabalhando na clínica {clinica.nome}.")
        return redirect(destino)
    return render(request, "core/trocar_clinica.html", {"clinicas": clinicas, "next": destino})


class TrocarSenhaView(PasswordChangeView):
    """Any logged-in user can change their own password (keeps the session open)."""

    form_class = TrocaSenhaForm
    template_name = "core/trocar_senha.html"
    success_url = reverse_lazy("inicio")

    def form_valid(self, form):
        messages.success(self.request, "Senha alterada.")
        return super().form_valid(form)
