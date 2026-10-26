from ninja import NinjaAPI

from apps.novidades.api import router as novidades_router
from apps.novidades.releases import versao_atual

api = NinjaAPI(
    title="Medical System API",
    version="1",
    description="API used by the mobile app (medical-system-app).",
    urls_namespace="api-v1",
)

api.add_router("/", novidades_router)


@api.get("/versao", auth=None, tags=["Sistema"])
def versao(request):
    """Current server version. The app uses it to check compatibility."""
    return {"versao": versao_atual()}
