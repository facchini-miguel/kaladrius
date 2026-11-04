from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.db import DatabaseError, connection
from ninja import NinjaAPI

from apps.whats_new.api import router as novidades_router
from apps.whats_new.releases import versao_atual

api = NinjaAPI(
    title=f"{settings.NOME_SISTEMA} API",
    version="1",
    description="API used by the mobile app (kaladrius-app).",
    urls_namespace="api-v1",
    # The interactive docs (/api/v1/docs) describe the API: superusers only. The app only
    # calls the endpoints, which keep their own access rules.
    docs_decorator=user_passes_test(lambda usuario: usuario.is_superuser),
)

api.add_router("/", novidades_router)


def _banco_responde():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return False
    return True


@api.get("/version", auth=None, tags=["System"])
def version(request):
    """Current server version. The app uses it to check compatibility."""
    return {"version": versao_atual()}


@api.get("/health", auth=None, tags=["System"])
def health(request):
    """For uptime monitors: 200 only when the database answers too (decision 079)."""
    if not _banco_responde():
        return api.create_response(request, {"database": False}, status=503)
    return {"database": True, "version": versao_atual()}


# The addresses and fields before decision 155, for monitors and scripts still using them: the
# server scripts of the previous version check a rolled-back app through /saude.
@api.get("/versao", auth=None, include_in_schema=False)
def versao(request):
    return {"versao": versao_atual()}


@api.get("/saude", auth=None, include_in_schema=False)
def saude(request):
    if not _banco_responde():
        return api.create_response(request, {"banco": False}, status=503)
    return {"banco": True, "versao": versao_atual()}
