from django.contrib import admin

from .models import Recall


@admin.register(Recall)
class RechamadaAdmin(admin.ModelAdmin):
    list_display = ["data", "patient", "descricao", "concluida", "clinic"]
    list_filter = ["clinic", "concluida"]
    search_fields = ["descricao", "patient__nome"]
    date_hierarchy = "data"
    raw_id_fields = ["patient"]
