from .record import context, request_ip


class AuditMiddleware:
    """Makes the current user and IP available to audit entries written during the request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user if request.user.is_authenticated else None
        with context(user, request_ip(request)):
            return self.get_response(request)
