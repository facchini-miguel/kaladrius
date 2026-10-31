from django.urls import path

from . import views

app_name = "pacientes"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("sugestoes/", views.sugestoes, name="sugestoes"),
    path("aniversariantes/", views.aniversariantes, name="aniversariantes"),
    path("<int:pk>/", views.ficha, name="ficha"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("<int:pk>/imprimir/", views.imprimir, name="imprimir"),
    path("<int:pk>/arquivar/", views.arquivar, name="arquivar"),
    path("<int:pk>/restaurar/", views.restaurar, name="restaurar"),
    path("<int:pk>/excluir/", views.excluir, name="excluir"),
    path("<int:pk>/relacionados/novo/", views.relacionado_novo, name="relacionado_novo"),
    path("relacionados/<int:pk>/", views.relacionado_editar, name="relacionado_editar"),
    path("relacionados/<int:pk>/remover/", views.relacionado_remover, name="relacionado_remover"),
]
