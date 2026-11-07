from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.db import DatabaseError, connection
from ninja import NinjaAPI

from apps.whats_new.api import router as whats_new_router
from apps.whats_new.releases import current_version

api = NinjaAPI(
    title=f"{settings.SYSTEM_NAME} API",
    version="1",
    description="API used by the mobile app (kaladrius-app).",
    urls_namespace="api-v1",
    # The interactive docs (/api/v1/docs) describe the API: superusers only. The app only
    # calls the endpoints, which keep their own access rules.
    docs_decorator=user_passes_test(lambda user: user.is_superuser),
)

api.add_router("/", whats_new_router)


def _database_answers():
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return False
    return True


@api.get("/version", auth=None, tags=["System"])
def version(request):
    """Current server version. The app uses it to check compatibility."""
    return {"version": current_version()}


@api.get("/health", auth=None, tags=["System"])
def health(request):
    """For uptime monitors: 200 only when the database answers too (decision 079)."""
    if not _database_answers():
        return api.create_response(request, {"database": False}, status=503)
    return {"database": True, "version": current_version()}
