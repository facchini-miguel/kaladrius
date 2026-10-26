from .registro import contexto, ip_da_requisicao


class AuditoriaMiddleware:
    """Makes the current user and IP available to audit entries written during the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = request.user if request.user.is_authenticated else None
        with contexto(usuario, ip_da_requisicao(request)):
            return self.get_response(request)
