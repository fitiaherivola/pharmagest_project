from django.contrib import admin

from .models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("nom", "telephone", "adresse", "est_actif", "date_creation")
    list_filter = ("est_actif",)
    search_fields = ("nom", "telephone", "adresse")
