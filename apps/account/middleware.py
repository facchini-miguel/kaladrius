from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from . import services

# Pages open to someone who still has to turn two-step verification on.
EXEMPT_PATHS = ["account:two_factor", "account:active", "logout", "change_language", "privacy"]


class RequireTwoFactorMiddleware:
    """Sends whoever the clinic requires to use two-step verification, and has not turned it
    on yet, to the page with the QR code (decision 112)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._pending(request):
            return redirect("account:two_factor")
        return self.get_response(request)

    def _pending(self, request):
        path = request.path_info
        if path.startswith((settings.STATIC_URL, "/admin/", "/api/")):
            return False
        if path in {reverse(name) for name in EXEMPT_PATHS}:
            return False
        if not services.is_required(request):
            return False
        return not services.active_for(request.user)
