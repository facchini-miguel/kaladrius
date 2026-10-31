from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from . import servicos

# Pages open to someone who still has to turn two-step verification on.
LIVRES = ["conta:duas_etapas", "conta:ativo", "logout", "trocar_idioma", "privacidade"]


class ExigirDuasEtapasMiddleware:
    """Sends whoever the clinic requires to use two-step verification, and has not turned it
    on yet, to the page with the QR code (decision 112)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._pendente(request):
            return redirect("conta:duas_etapas")
        return self.get_response(request)

    def _pendente(self, request):
        caminho = request.path_info
        if caminho.startswith((settings.STATIC_URL, "/admin/", "/api/")):
            return False
        if caminho in {reverse(nome) for nome in LIVRES}:
            return False
        if not servicos.obrigatoria(request):
            return False
        return not servicos.ativa_para(request.user)
