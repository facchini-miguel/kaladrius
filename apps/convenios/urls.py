from django.urls import path

from . import views

app_name = "convenios"

urlpatterns = [
    path("", views.lista, name="lista"),
    path("novo/", views.novo, name="novo"),
    path("<int:pk>/editar/", views.editar, name="editar"),
    path("carteirinhas/nova/<int:paciente>/", views.carteirinha_nova, name="carteirinha_nova"),
    path("carteirinhas/<int:pk>/editar/", views.carteirinha_editar, name="carteirinha_editar"),
]
