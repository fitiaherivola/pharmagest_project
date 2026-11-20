from django.contrib import admin

from .models import Fournisseur


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ("nom", "contact_principal", "telephone", "email", "est_actif")
    list_filter = ("est_actif",)
    search_fields = ("nom", "contact_principal", "telephone", "email", "numero_fiscal")
