from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from . import services

# Pages open to someone who still has to turn two-step verification on.
LIVRES = ["account:two_factor", "account:active", "logout", "change_language", "privacy"]


class ExigirDuasEtapasMiddleware:
    """Sends whoever the clinic requires to use two-step verification, and has not turned it
    on yet, to the page with the QR code (decision 112)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._pendente(request):
            return redirect("account:two_factor")
        return self.get_response(request)

    def _pendente(self, request):
        caminho = request.path_info
        if caminho.startswith((settings.STATIC_URL, "/admin/", "/api/")):
            return False
        if caminho in {reverse(name) for name in LIVRES}:
            return False
        if not services.obrigatoria(request):
            return False
        return not services.ativa_para(request.user)
