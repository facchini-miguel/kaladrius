from django.contrib import admin

from .models import Recall


@admin.register(Recall)
class RechamadaAdmin(admin.ModelAdmin):
    list_display = ["date", "patient", "description", "concluida", "clinic"]
    list_filter = ["clinic", "concluida"]
    search_fields = ["description", "patient__name"]
    date_hierarchy = "date"
    raw_id_fields = ["patient"]
